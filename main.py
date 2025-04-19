import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path

# —— 跨平台读取按键 ——
if sys.platform == 'win32':
    import msvcrt
else:
    import tty
    import termios

class SimpleMenu:
    def __init__(self, options):
        self.options = options
        self.selected = 0
        self._print_menu()

    def _print_menu(self):
        sys.stdout.write("\033[{}A".format(len(self.options)))
        for i, opt in enumerate(self.options):
            prefix = "\033[1;32m>>>\033[0m" if i == self.selected else "   "
            line = f"{prefix} \033[1m{opt}\033[0m" if i == self.selected else f"{prefix} {opt}"
            sys.stdout.write("\033[K" + line + "\n")
        sys.stdout.flush()

    def run(self):
        while True:
            key = self._get_key()
            if key == 'up' and self.selected > 0:
                self.selected -= 1
                self._print_menu()
            elif key == 'down' and self.selected < len(self.options) - 1:
                self.selected += 1
                self._print_menu()
            elif key == 'enter':
                return self.options[self.selected]
            elif key in ['esc', 'ctrl_c']:
                return None

    def _get_key(self):
        if sys.platform == 'win32':
            ch = msvcrt.getch()
            if ch == b'\xe0':
                ch = msvcrt.getch()
                return {'H': 'up', 'P': 'down', 'M': 'right', 'K': 'left'}.get(ch.decode(), '')
            elif ch == b'\r':
                return 'enter'
            elif ch == b'\x1b':
                return 'esc'
            elif ch == b'\x03':  # 捕获 Windows 的 Ctrl+C
                return 'ctrl_c'
        else:
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
                if ch == '\x1b':
                    ch = sys.stdin.read(2)
                    return {'[A': 'up', '[B': 'down', '[C': 'right', '[D': 'left'}.get(ch, '')
                elif ch == '\n':
                    return 'enter'
                elif ch == '\x03':  # 捕获 Unix 的 Ctrl+C
                    return 'ctrl_c'
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ''

def select_csv_file(directory):

    files = [f for f in os.listdir(directory) if f.endswith('.csv')]

    print("\n Use ↑↓ to choose，回车确认:\n")  # here didn't work
    menu = SimpleMenu(files)
    selected = menu.run()
    return os.path.join(directory, selected) if selected else None


def get_std_size() -> float:
    """提示用户输入 std_size 并返回验证后的浮点数"""
    while True:
        try:
            std_size = float(input("请输入你实际所用混标的份数: "))
            if std_size <= 0:
                print("错误: 必须为正数，请重新输入")
            else:
                return std_size
        except ValueError:
            print("错误: 请输入有效数字")


def process_and_export(
    tracefinder_csv_path: str,
    stdcurve_csv_path: str,
    std_size: float,
    result1_suffix: str = "_result1_提取CompoundFinenameArea",
    result2_suffix: str = "_result2_不具有标准曲线的",
    result3_suffix: str = "_result3_外标法转换后",
    result4_suffix: str = "_result4_检查ISTD",
    result5_suffix: str = "_result5_pmol"
):
    # —— 1. 读取表格 A 并提取关键列 —— #
    df = pd.read_csv(tracefinder_csv_path)
    df.columns = df.columns.str.strip()


    # —— 2. 读取标准曲线表 B 并转化 —— #
    stdcurve = pd.read_csv(stdcurve_csv_path)
    stdcurve.columns = stdcurve.columns.str.strip()
    stdcurve[["a", "b"]] = stdcurve["formula"].str.extract(
        r"lg\(area\)=([\d\.]+)lg\(pmol\)\+([\d\.]+)"
    ).astype(float)
    stdcurve = stdcurve.drop(columns="formula")
    stdcurve["applyto"] = stdcurve["applyto"].str.split(",").map(
        lambda x: [s.strip() for s in x]
    )
    stdcurve_table = stdcurve.explode("applyto")
    stdcurve_table['amount'] = stdcurve_table['amount'] * std_size

    # —— 3. 计算 —— #
    needed = ["Compound", "Filename", "Area"]
    df_result1 = df[needed].copy()
    df_result1["Area"] = pd.to_numeric(
        df_result1["Area"],
        errors="coerce",  # 将非数值转为NaN
        downcast="float"  # 自动向下转换为最节省内存的数值类型
    )
    df_result1 = df_result1.rename(columns={"Compound": "var"})

    df_with_category = df_result1.assign(
        category=lambda x: x["var"].str.extract(r"(\S+)", expand=False)
    )

    df_result2 = df_with_category[~df_with_category["category"].isin(stdcurve_table["applyto"])].loc[:, ["var", "Filename", "Area"]]

    merged_df = pd.merge(
        df_with_category,
        stdcurve_table,
        how="inner",
        left_on="category",
        right_on="applyto"
    )
    merged_df["pmol_ES"] = 10 ** ((np.log10(merged_df["Area"]) - merged_df["b"]) / merged_df["a"])

    df_result4 = (
        merged_df[merged_df["var"].str.contains("ISTD")]
        .assign(recovery=lambda x: x["pmol_ES"] / x["amount"])
    )

    df_result5 = (
        pd.merge(
            merged_df,
            df_result4[["Filename", "component", "recovery"]],
            how="left",
            on=["Filename", "component"]
        )
        .assign(
            pmol_ES_IS=lambda x: x["pmol_ES"] / x["recovery"]
        )
        .loc[lambda x: ~x["var"].str.contains("ISTD", na=False)]
    )

    df_result3 = merged_df.loc[:, ["var", "Filename", "pmol_ES"]]
    df_result4 = df_result4.loc[:, ["var", "Filename", "pmol_ES"]]
    df_result5 = df_result5.loc[:, ["var", "Filename", "pmol_ES_IS"]]


    # —— 5. 构造输出文件名 & 导出 —— #
    path_obj  = Path(tracefinder_csv_path)
    base_path = path_obj.parent / path_obj.stem
    # 定义结果文件名后缀和对应的DataFrame
    results = [
        (result1_suffix, df_result1),
        (result2_suffix, df_result2),
        (result3_suffix, df_result3),
        (result4_suffix, df_result4),
        (result5_suffix, df_result5)
    ]

    for suffix, df in results:
        wide_df = df.pivot_table(index=df.columns[0], columns=df.columns[1], values=df.columns[2], dropna=False, sort=False)
        wide_df = wide_df.reset_index()
        write_csv_path = f"{base_path}{suffix}.csv"
        wide_df.to_csv(write_csv_path, index=False, encoding="utf-8-sig")
        print(f"- \u2713 Successfully exported: {write_csv_path}")


def main():
    print("TraceFinder CSV to Matrix")
    print("-------------------------")
    path_a = input("TraceFinder CSV path: ").strip().strip('"')

    stdcurve_dir = "stdcurve"
    print("Select a stdcurve CSV file: ")
    stdcurve_csv = select_csv_file(stdcurve_dir)
    if stdcurve_csv:
        print(f"\n\033[1;32m✓ 已选择文件: {stdcurve_csv}\033[0m")
    else:
        print("\n\033[31m× 未选择文件\033[0m")


    std_size = get_std_size()

    try:
        process_and_export(path_a, stdcurve_csv, std_size)
        print("✅ 全部处理完成！")
    except Exception as e:
        print("❌ 处理失败：", e)

if __name__ == "__main__":
    main()

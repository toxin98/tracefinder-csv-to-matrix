import pandas as pd
import numpy as np
import datetime
from pathlib import Path

def get_standard_size() -> float:
    """提示用户输入 standard_size 并返回验证后的浮点数"""
    while True:
        try:
            standard_size = float(input("请输入你实际所用混标的份数: "))
            if standard_size <= 0:
                print("Error: 必须为正数，请重新输入")
            else:
                return standard_size
        except ValueError:
            print("Error: 请输入有效数字")

def process_and_export(
    tracefinder_csv_path: str,
    standardcurve_csv_path: str,
    standard_size: float,
    result01_suffix: str = "_01subset",  # 提取CompoundFinenameArea
    result02_suffix: str = "_02unquantified",  # 不具有标准曲线的
    result03_suffix: str = "_03quantified",  # 外标法转换后
    result04_suffix: str = "_04standards",  # 检查ISTD
    result05_suffix: str = "_matrix"   # 根据ISTD回收率计算样品中总的pmol
):

    # —— 1. 读取表格 A 并提取关键列 —— #
    tracefinder_csv_path = tracefinder_csv_path.strip().strip('"')
    df = pd.read_csv(tracefinder_csv_path)
    df.columns = df.columns.str.strip()

    # —— 2. 读取标准曲线表 B 并转化 —— #
    standardcurve_csv_path = standardcurve_csv_path.strip().strip('"')
    standardcurve = pd.read_csv(standardcurve_csv_path)
    standardcurve.columns = standardcurve.columns.str.strip()
    standardcurve[["a", "b"]] = standardcurve["formula"].str.extract(
        r"lg\(area\)=([\d\.]+)lg\(pmol\)\+([\d\.]+)"
    ).astype(float)
    standardcurve = standardcurve.drop(columns="formula")
    standardcurve["applyto"] = standardcurve["applyto"].str.split(",").map(
        lambda x: [s.strip() for s in x]
    )
    standardcurve_table = standardcurve.explode("applyto")
    standardcurve_table['amount'] = standardcurve_table['amount'] * standard_size

    # —— 3. 计算 —— #
    needed = ["Compound", "Filename", "Area"]
    df_result01 = df[needed].copy()
    df_result01["Area"] = pd.to_numeric(
        df_result01["Area"],
        errors="coerce",  # 将非数值转为NaN
        downcast="float"  # 自动向下转换为最节省内存的数值类型
    )
    df_result01 = df_result01.rename(columns={"Compound": "var"})

    df_with_category = df_result01.assign(
        category=lambda x: x["var"].str.extract(r"(\S+)", expand=False)
    )

    df_result02 = df_with_category[~df_with_category["category"].isin(standardcurve_table["applyto"])].loc[:, ["var", "Filename", "Area"]]

    merged_df = pd.merge(
        df_with_category,
        standardcurve_table,
        how="inner",
        left_on="category",
        right_on="applyto"
    )
    merged_df["pmol_ES"] = 10 ** ((np.log10(merged_df["Area"]) - merged_df["b"]) / merged_df["a"])

    df_result04 = (
        merged_df[merged_df["var"].str.contains("ISTD")]
        .assign(recovery=lambda x: x["pmol_ES"] / x["amount"])
    )

    df_result05 = (
        pd.merge(
            merged_df,
            df_result04[["Filename", "component", "recovery"]],
            how="left",
            on=["Filename", "component"]
        )
        .assign(
            pmol_ES_IS=lambda x: x["pmol_ES"] / x["recovery"]
        )
        .loc[lambda x: ~x["var"].str.contains("ISTD", na=False)]
    )

    df_result03 = merged_df.loc[:, ["var", "Filename", "pmol_ES"]]
    df_result04 = df_result04.loc[:, ["var", "Filename", "pmol_ES"]]
    df_result05 = df_result05.loc[:, ["var", "Filename", "pmol_ES_IS"]]

    # —— 4. 构造输出文件名 & 导出 —— #
    path_obj  = Path(tracefinder_csv_path)
    base_path = path_obj.parent / path_obj.stem
    # 定义结果文件名后缀和对应的DataFrame
    results = [
        (result01_suffix, df_result01),
        (result02_suffix, df_result02),
        (result03_suffix, df_result03),
        (result04_suffix, df_result04),
        (result05_suffix, df_result05)
    ]

    for suffix, df in results:
        wide_df = df.pivot_table(index=df.columns[0], columns=df.columns[1], values=df.columns[2], dropna=False, sort=False)
        wide_df = wide_df.reset_index()
        write_csv_path = f"{base_path}{suffix}.csv"
        wide_df.to_csv(write_csv_path, index=False, encoding="utf-8-sig")
        print(f"- \u2713 Successfully exported: {write_csv_path}")

    # —— 5. 日志记录 —— #
    log_file = path_obj.parent / "matrix_log.txt"
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"Last run: {datetime.datetime.now()}\n")
        f.write(f"standardcurve file: {Path(standardcurve_csv_path).name}\n")

def main():
    print("TraceFinder CSV to Matrix")
    print("-------------------------")
    path_a = input("TraceFinder CSV path: ")

    path_b = input("StandardCurve CSV path: ")

    standard_size = get_standard_size()

    try:
        process_and_export(path_a, path_b, standard_size)
        print("✅ Processing complete!")
    except Exception as e:
        print("❌ Processing failed: ", e)

if __name__ == "__main__":
    main()

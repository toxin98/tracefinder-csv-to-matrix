# TraceFinder CSV to Matrix

将TraceFinder导出的csv文件转化成matrix矩阵。

## 如何在科研项目中使用

假设你有科研项目"AzoSM"，路径为`"D:\science\projects\AzoSM"`

将`tracefinder-csv-to-matrix.py`放到`AzoSM/src/`下

使用uv管理

```bash
uv install pandas
```

## 对某个csv使用

```bash
cd "D:\science\projects\AzoSM"
uv run python tracefinder-csv-to-matrix.py
```

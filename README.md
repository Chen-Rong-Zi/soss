# SOSS (Secure Object Storage Service)

将指定文件夹上传到阿里云OSS
受@gaogaotiantian启发，使用dry-python/returns重写为函数式编程风格的命令行网盘工具

## 准备工作

```
pip install -r requirements.txt
```

在你的阿里云管理系统内，找到下面的内容：
* OSS Bucket的endpoint（例如`oss-cn-hangzhou.aliyuncs.com`）
* OSS Bucket的名字
* 你的用户的access key（推荐使用RAM用户）
    * `export OSS_ACCESS_KEY_ID=<KEY ID>`
    * `export OSS_ACCESS_KEY_SECRET=<KEY SECRET>`

在`config.json`中指定`endpoint`和`bucket`

## 使用说明

### 上传文件

```
python soss.py upload -k my_password text.txt image.png

# 支持上传整个文件夹的内容，文件夹所有内容会保持结构上传到bucket根目录
python soss.py upload -k my_password data/
```
## 8月1日更新
- feature: 使用迭代器 减小内存占用
- feature: 新增上传文件前云存储中判断是否存在，根据哈希值判断是否需要上传覆盖

## 8月5日更新
- feature: 新增多线程支持

## 8月12日更新
- feature: 兼容windows\unix

### LICENSE

Copyright 2024 RongZi Chen.

Distributed under the terms of the [Apache 2.0 license](LICENSE)

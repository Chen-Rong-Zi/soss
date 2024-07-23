# SOSS (Secure Object Storage Service)

一个可以在把文件上传到阿里云OSS的小工具，使用dry-python/returns重写为函数式风格

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

在`config.json`中，配置好`endpoint`和`bucket`。如果不想使用`config.json`，也可以在命令行作为参数输入。

## 使用说明

### 上传文件

```
python soss.py upload -k my_password text.txt image.png

# 支持上传整个文件夹的内容，文件夹所有内容会保持结构上传到bucket根目录
python soss.py upload -k my_password data/
```
# todo

### 文件列表

```
# 如果配置好了config.json
python soss.py list
python soss.py list --prefix data/

# 如果想在命令行输入bucket和endpoint
python soss.py list -b bucket_name -e endpoint
```

### 下载文件

```
python soss.py download -k my_password text.txt image.png

# 指定保存文件夹
python soss.py download -k my_password --output_dir ./data text.txt image.png

# 剩下的参数和upload一样
```

### LICENSE

Copyright 2024 Tian Gao.
Copyright 2024 RongZi Chen.

Distributed under the terms of the [Apache 2.0 license](LICENSE)

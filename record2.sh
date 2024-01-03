#!/bin/bash

# python3 start.py -root_path dmf/ -choice 2 -app_path 目标应用的apk所在目录 -json_name 录制好的dmf所存的文件夹名称 -device_serial 安卓设备的设备号
python3 ./code/start.py -root_path dmf/ -choice 2 -app_path ./app/amaze.apk  -json_name _amaze  -device_serial emulator-5554

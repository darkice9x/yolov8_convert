# yolov8_convert

cd ~/Work/airockchip

git clone -b rk_opt_v1 https://github.com/airockchip/ultralytics_yolov8.git

mv ultralytics_yolov8 yolov8

cd yolov8

conda create -n yolov8_opt1 python=3.11

conda activate yolov8_opt1

pip install -r requirements.txt

Download yolov8s.pt

wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8s.pt

torchscript generating

from ultralytics import YOLO

model = YOLO( "yolov8s.pt" )

path = model.export( format = "rknn" )

generating below file

yolov8s_rknnopt.torchscript

cd ~/Work

git clone https://github.com/rockchip-linux/rknn-toolkit2.git

conda create -n rknn220 python=3.12

conda activate rknn

pip install ~/Work/rknn-toolkit2/packages/rknn_toolkit2-2.2.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl

pip install ruamel.yaml==0.17.21

git clone https://github.com/darkice9x/yolov8_convert

cd yolov8_convert/convert

cp ~/Work/airockchip/yolov8/yolov8s_rknnopt.torchscript ./

nano yolov8.yml

python ./common/rknn_converter/rknn_convert.py --yml_path ./yolov8.yml


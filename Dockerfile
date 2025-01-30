#################################################
#          Dockerfile to run RTSP2WEB           #
#           Based on a Python Image             #
#################################################

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y libgl1-mesa-glx libglib2.0-0 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* 

COPY . /app

RUN pip3 install --no-cache-dir -r requirements.txt

CMD ["python3", "main.py"] 

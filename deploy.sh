#!/bin/bash

# 서버 정보 설정
SSH_USER="eunsung"
SSH_HOST="eunsung-server"
SSH_PATH="/home/eunsung/Desktop/Code"
SSH_KEY="~/.ssh/id_ed25519"  # SSH 키 경로

# 서버에 파일 복사
echo "Copying files to server..."
scp -i $SSH_KEY -r ./* $SSH_USER@$SSH_HOST:$SSH_PATH

# .env 파일 별도 복사 (숨김 파일이므로 별도로 복사)
echo "Copying .env file to server..."
scp -i $SSH_KEY .env $SSH_USER@$SSH_HOST:$SSH_PATH

# 서버에서 명령어 실행
echo "Executing commands on server..."
ssh -i $SSH_KEY $SSH_USER@$SSH_HOST "
    cd $SSH_PATH && \
    # 가상환경 생성 및 활성화
    python3 -m venv venv && \
    source venv/bin/activate && \
    # 의존성 설치
    pip install -r requirements.txt && \
    # 스크립트 실행 권한 부여
    chmod +x start_monitoring.sh && \
    ./start_monitoring.sh && \
    # 스케줄러를 백그라운드에서 실행
    nohup python scheduler.py > scheduler.log 2>&1 &
    # 스케줄러 프로세스 확인
    echo 'Checking scheduler process...'
    ps aux | grep '[p]ython.*scheduler.py'
    # 로그 파일 확인
    echo 'Checking scheduler logs...'
    tail -n 5 scheduler.log
"

echo "Deployment completed!"
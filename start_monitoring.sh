#!/bin/bash
# AutoBlog 모니터링 시스템 시작 스크립트

echo "AutoBlog 모니터링 시스템 시작 중..."

# Docker Compose로 모니터링 컨테이너 시작
echo "모니터링 컨테이너 시작 중..."
docker-compose -f docker-compose-monitoring.yml up -d

if [ $? -ne 0 ]; then
    echo "오류: Docker 컨테이너 시작 실패! Docker가 설치되어 있고 실행 중인지 확인하세요."
    exit 1
fi

echo "모니터링 컨테이너가 시작되었습니다."
echo "Grafana 대시보드: http://localhost:3000 (계정: admin/autoblog)"

# 메트릭 익스포터 백그라운드에서 실행
echo "메트릭 익스포터 시작 중..."
python run_monitoring.py &
EXPORTER_PID=$!

echo ""
echo "AutoBlog 모니터링 시스템이 성공적으로 시작되었습니다!"
echo "메트릭 익스포터 PID: $EXPORTER_PID"
echo "모니터링을 종료하려면 CTRL+C를 누르세요."
echo ""

# PID 저장
echo $EXPORTER_PID > .monitoring.pid

# 종료 시 정리 함수
function cleanup {
    echo "모니터링 시스템 종료 중..."
    
    # 익스포터 종료
    if [ -f .monitoring.pid ]; then
        PID=$(cat .monitoring.pid)
        kill $PID 2>/dev/null
        rm .monitoring.pid
    fi
    
    # Docker 컨테이너 종료
    docker-compose -f docker-compose-monitoring.yml down
    
    echo "모니터링 시스템이 종료되었습니다."
    exit 0
}

# 중단 시그널 처리
trap cleanup SIGINT SIGTERM

# 메인 프로세스가 종료되지 않도록 대기
while true; do
    sleep 1
done 
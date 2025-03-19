@echo off
REM AutoBlog 모니터링 시스템 시작 스크립트

echo AutoBlog 모니터링 시스템 시작 중...

REM Docker Compose로 모니터링 컨테이너 시작
echo 모니터링 컨테이너 시작 중...
docker-compose -f docker-compose-monitoring.yml up -d

if %ERRORLEVEL% neq 0 (
    echo 오류: Docker 컨테이너 시작 실패!
    pause
    exit /b %ERRORLEVEL%
)

echo 모니터링 컨테이너가 시작되었습니다.
echo Grafana 대시보드: http://localhost:3000 (계정: admin/autoblog)

REM 메트릭 익스포터 백그라운드에서 실행
echo 메트릭 익스포터 시작 중...
start "AutoBlog Metrics Exporter" python run_monitoring.py

echo.
echo AutoBlog 모니터링 시스템이 성공적으로 시작되었습니다!
echo 모니터링을 종료하려면 이 창을 닫고 Docker Desktop에서 컨테이너를 중지하세요.
echo.

pause 
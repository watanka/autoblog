# AutoBlog 스케줄러를 Windows 서비스로 설치하는 스크립트
# 관리자 권한으로 실행해야 합니다

# NSSM (Non-Sucking Service Manager)을 사용하여 서비스 설치
# https://nssm.cc/download 에서 NSSM을 다운로드하고 PATH에 추가해야 합니다

$ErrorActionPreference = "Stop"

# 현재 스크립트의 경로에서 상위 디렉토리(프로젝트 루트)로 이동
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Get-Item $scriptPath).Parent.FullName

Write-Host "AutoBlog 프로젝트 경로: $projectRoot"

# Python 경로 확인
$pythonPath = (Get-Command python).Source
if (-not $pythonPath) {
    Write-Error "Python이 설치되지 않았거나 PATH에 추가되지 않았습니다."
    exit 1
}

Write-Host "Python 경로: $pythonPath"

# NSSM 경로 확인
$nssmPath = (Get-Command nssm -ErrorAction SilentlyContinue).Source
if (-not $nssmPath) {
    Write-Error "NSSM이 설치되지 않았거나 PATH에 추가되지 않았습니다."
    Write-Host "NSSM은 https://nssm.cc/download 에서 다운로드할 수 있습니다."
    exit 1
}

Write-Host "NSSM 경로: $nssmPath"

# 서비스 이름 및 설정
$serviceName = "AutoBlogScheduler"
$serviceDescription = "AutoBlog 블로그 자동화 스케줄러 서비스"
$schedulerScript = Join-Path $projectRoot "scheduler.py"

# 서비스가 이미 존재하는지 확인
$existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Warning "서비스 '$serviceName'이(가) 이미 존재합니다. 기존 서비스를 제거합니다."
    nssm remove $serviceName confirm
}

# 서비스 설치
Write-Host "서비스 '$serviceName' 설치 중..."
nssm install $serviceName $pythonPath
nssm set $serviceName AppParameters "$schedulerScript"
nssm set $serviceName AppDirectory $projectRoot
nssm set $serviceName DisplayName $serviceName
nssm set $serviceName Description $serviceDescription
nssm set $serviceName Start AUTO_START
nssm set $serviceName AppStdout "$projectRoot\logs\service_stdout.log"
nssm set $serviceName AppStderr "$projectRoot\logs\service_stderr.log"
nssm set $serviceName AppRotateFiles 1
nssm set $serviceName AppRotateOnline 1
nssm set $serviceName AppRotateSeconds 86400

# 서비스 시작
Write-Host "서비스 '$serviceName' 시작 중..."
Start-Service -Name $serviceName

# 상태 확인
$service = Get-Service -Name $serviceName
Write-Host "서비스 상태: $($service.Status)"

Write-Host "설치 완료!"
Write-Host "서비스를 관리하려면 다음 명령어를 사용하세요:"
Write-Host "  - 상태 확인: Get-Service -Name $serviceName"
Write-Host "  - 시작: Start-Service -Name $serviceName"
Write-Host "  - 중지: Stop-Service -Name $serviceName"
Write-Host "  - 제거: nssm remove $serviceName confirm" 
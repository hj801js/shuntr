# Shunt Reactor Engineering

지중 케이블 충전전류, 무효전력, 개폐전류 검토 보고서를 생성하는 엔지니어링 도구입니다.
기존 PySide6 데스크톱 앱을 유지하면서, 동일한 계산/리포트 엔진을 재사용하는 FastAPI 기반 웹앱도 함께 제공합니다.

## 웹앱 실행

1. 의존성 설치

```bash
pip install -e .
```

2. 웹 서버 실행

```bash
uvicorn shunt_reactor_engineering.web.main:app --host 127.0.0.1 --port 8000
```

또는 콘솔 스크립트 사용:

```bash
shunt-reactor-web
```

3. 브라우저 접속

```text
http://127.0.0.1:8000
```

웹앱 기능:
- 계산 입력 폼
- 충전전류/무효전력/개폐전류 결과 표시
- PDF 보고서 다운로드

## 데스크톱 앱 실행

```powershell
.\activate_power_conda.ps1
python -m shunt_reactor_engineering
```

## Quick Start

1. 워크스페이스 로컬 Conda 환경을 준비합니다.

```powershell
$env:CONDA_ENVS_PATH = "$PWD/.conda_envs"
$env:CONDA_PKGS_DIRS = "$PWD/.conda_pkgs"
conda env update -p "$PWD/.conda_envs/shuntreactorengineering" -f environment.yml --prune
```

2. 테스트를 실행합니다.

```powershell
pytest
```

3. 앱을 실행합니다.

```powershell
python -m shunt_reactor_engineering
```

VS Code는 `.conda_envs/shuntreactorengineering` 환경을 바로 인식하도록 설정되어 있습니다.

## Docker 배포

이미지 빌드:

```bash
docker build -t shuntreactor-web .
```

컨테이너 실행:

```bash
docker run --rm -p 8000:8000 \
  -e SHUNT_REACTOR_OUTPUT_DIR=/app/output \
  -e SHUNT_REACTOR_RUNTIME_DIR=/app/output/runtime \
  shuntreactor-web
```

배포 메모:
- Docker 이미지에는 `xelatex`와 `fonts-noto-cjk`를 포함해 PDF 생성을 지원합니다.
- 앱은 `PORT`, `SHUNT_REACTOR_OUTPUT_DIR`, `SHUNT_REACTOR_RUNTIME_DIR` 환경 변수로 서버 포트와 저장 경로를 제어할 수 있습니다.
- 루트의 `render.yaml`을 사용하면 Render에서 바로 Docker 웹 서비스로 연결할 수 있습니다.
- Render/Railway/VPS 등 Docker 지원 환경에 배포할 수 있습니다.

## Report App

앱 기능:

- 충전전류 계산
- 무효전력 계산
- 개폐전류 검토
- PDF 미리보기
- 최신 PDF 바로 열기
- 출력 폴더 바로 열기
- 관리자 로그인 후 케이블 정전용량/로고 경로 수정

기본값:

- 프로젝트명: `재생에너지 연계 변전소`
- 회선 수: `1`
- 케이블: `154kV XLPE 1200 mm²`
- 기본 로고 경로: `data/uptec_logo.jpg`

관리자 기본 계정:

- 사용자명: `admin`
- 비밀번호: `uptec`

환경 변수 `SHUNT_REACTOR_ADMIN_USER`, `SHUNT_REACTOR_ADMIN_PASSWORD`로 변경할 수 있습니다.

생성 파일은 `output/reports`에 저장되고, 관리자 설정은 `output/config/app_settings.json`에 저장됩니다.

## Layout

- `src/shunt_reactor_engineering`: 계산 및 UI 코드
- `src/shunt_reactor_engineering/web`: FastAPI 웹앱 코드
- `tests`: 회귀 테스트
- `data`: 로고 및 입력 자료
- `scripts/build_and_smoke.ps1`: onefile EXE 빌드/스모크 테스트
- `references/release-layout.md`: 권장 배포 폴더 구조

## Packaging

- `PACKAGING.md`: 런타임 경로 규칙
- `scripts/build_and_smoke.ps1`: Nuitka onefile 빌드 스크립트

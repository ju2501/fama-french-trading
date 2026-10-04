# SNU Alpha — Quant Models

퀀트 전략과 거래 API를 실습한 Python 노트북 모음입니다.

| 노트북 | 내용 |
| --- | --- |
| [EMAcross.ipynb](Quant_models/EMAcross.ipynb) | Finter 기반 50/200일 EMA 신호 및 시뮬레이션 |
| [fibonacci.ipynb](Quant_models/fibonacci.ipynb) | Finter 기반 피보나치 되돌림 신호 및 시뮬레이션 |
| [fama_french.ipynb](Quant_models/fama_french.ipynb) | 암호화폐용 대체 팩터, 기술적 지표 및 백테스트 실습 |
| [autotrading_korbit.ipynb](Quant_models/autotrading_korbit.ipynb) | Korbit API 연동과 이동평균 기반 자동거래 실습 |

## 실행 환경

Python 3 기반 Jupyter Notebook 또는 Google Colab에서 열 수 있습니다.
각 노트북의 설치 셀에 필요한 패키지가 기재되어 있습니다.

- EMA와 Fibonacci 노트북은 Finter API 및 해당 데이터에 대한 접근 권한이 필요합니다. 실행 전에 `FINTER_API_KEY` 환경변수를 설정하세요.
- Fama-French 노트북의 `main()`은 데모 모드로 Yahoo Finance 데이터를 사용합니다. Korbit 인증 설정은 `KORBIT_API_KEY`, `KORBIT_API_SECRET` 환경변수에서 읽습니다.
- Korbit 자동거래 노트북은 실행 시 `getpass`로 인증 정보를 입력받습니다. 실제 주문을 전송하는 코드가 포함되어 있습니다.

## 코드 상태

학습·실험용 코드이며, 현재 API 호환성과 실행 결과는 검증하지 않았습니다.
Fama-French 노트북은 변동성·평균회귀 등을 대체 팩터로 사용하는 실험으로, 표준 주식 3요인 모델의 재현을 의미하지 않습니다.

인증 정보는 코드나 노트북 출력에 저장하지 마세요.

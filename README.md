# Fama–French Trading

퀀트 전략 실습과 한국 주식 Fama–French 5요인 모델을 모아 둔 저장소입니다.

## 폴더 안내

| 폴더 | 내용 | 시작하기 |
| --- | --- | --- |
| [stock_ff5](stock_ff5/) | 한국 주식 5요인 회귀, 월별 백테스트, 한국투자증권 모의·실전 주문 연동 | [설치·실행 설명서](stock_ff5/README.md) |
| [Quant_models](Quant_models/) | 기존 Finter 전략 및 Korbit 가상화폐 노트북 실습 | 아래 노트북 목록 참고 |

## 한국 주식 FF5

주식 자동매매 코드는 **[stock_ff5](stock_ff5/)**에서 확인하세요.
시장·규모·가치·수익성·투자 5요인을 사용하며, 한국 시장의 요인·총수익률 데이터와 KIS 인증정보는 별도로 준비해야 합니다.

저장소 최상위에서 API 없이 합성 예제를 실행할 수 있습니다.

```bash
python -m pip install -r stock_ff5/requirements.txt
python -m stock_ff5 demo --out stock_ff5/data/demo
python -m stock_ff5 signal --data stock_ff5/data/demo --as-of 2026-01-16 --out stock_ff5/output/demo-signal.json
python -m stock_ff5 backtest --data stock_ff5/data/demo --out stock_ff5/output/demo-backtest.csv
```

`demo`의 출력 경로는 비어 있어야 합니다. 합성 예제는 실제 투자성과가 아닙니다.
주문 기본 환경은 모의투자이며, 주문 전송에는 별도 실행 옵션이 필요합니다.
자세한 데이터 형식, 주문 조건, 검증 범위는 [설명서](stock_ff5/README.md)를 참고하세요.

## 기존 Quant 노트북

| 노트북 | 내용 |
| --- | --- |
| [EMAcross.ipynb](Quant_models/EMAcross.ipynb) | Finter 기반 50/200일 EMA 신호 및 시뮬레이션 |
| [fibonacci.ipynb](Quant_models/fibonacci.ipynb) | Finter 기반 피보나치 되돌림 신호 및 시뮬레이션 |
| [fama_french.ipynb](Quant_models/fama_french.ipynb) | 암호화폐용 대체 팩터·기술적 지표·백테스트 실습 |
| [autotrading_korbit.ipynb](Quant_models/autotrading_korbit.ipynb) | Korbit API와 이동평균 기반 자동거래 실습 |

노트북은 Python 3 기반 Jupyter 또는 Google Colab에서 열 수 있습니다.
패키지는 각 노트북의 설치 셀에 기재되어 있습니다.

- EMA·Fibonacci 노트북은 Finter 데이터 접근 권한과 `FINTER_API_KEY` 환경변수가 필요합니다.
- 가상화폐 Fama–French 노트북은 변동성·평균회귀 등을 대체 팩터로 쓰는 실습이며, 표준 주식 5요인 모델과 구분됩니다. Korbit 인증 설정은 `KORBIT_API_KEY`, `KORBIT_API_SECRET` 환경변수에서 읽습니다.
- Korbit 자동거래 노트북은 `getpass`로 인증정보를 입력받으며 실제 주문 코드가 포함되어 있습니다.

기존 노트북의 현재 API 호환성과 실제 거래 실행은 검증하지 않았습니다.
인증정보는 코드·노트북 출력·Git에 저장하지 마세요.

## 정리 이력

트레이딩과 무관한 LLM·OpenCV·약학·단백질 설계 실습 폴더를 현재 브랜치에서 정리했습니다.
이전 파일은 Git 커밋 기록에서 확인할 수 있습니다.

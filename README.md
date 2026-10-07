# Fama–French Trading

퀀트 전략 실습과 한국 주식 Fama–French 5요인 모델을 모아 둔 저장소입니다.

A repository of quantitative trading exercises and a Fama–French five-factor model for Korean equities.

## 폴더 안내 / Repository layout

| 폴더 / Folder | 내용 / Description | 시작하기 / Getting started |
| --- | --- | --- |
| [stock_ff5](stock_ff5/) | 한국 주식 5요인 회귀, 월별 백테스트, 한국투자증권 모의·실전 주문 연동 / Korean equity FF5 regression, monthly backtesting, and Korea Investment & Securities (KIS) paper/live order integration | [설치·실행 설명서 / Setup and usage](stock_ff5/README.md) |
| [Quant_models](Quant_models/) | 기존 Finter 전략 및 Korbit 가상화폐 노트북 실습 / Legacy Finter strategies and Korbit cryptocurrency notebook exercises | 아래 노트북 목록 참고 / See the notebook list below |

## 한국 주식 FF5 / Korean equity FF5

주식 자동매매 코드는 **[stock_ff5](stock_ff5/)**에서 확인하세요.
시장·규모·가치·수익성·투자 5요인을 사용하며, 한국 시장의 요인·총수익률 데이터와 KIS 인증정보는 별도로 준비해야 합니다.

The stock trading implementation is in **[stock_ff5](stock_ff5/)**. It uses the market, size, value, profitability, and investment factors. You must separately provide Korean-market factor returns, stock total returns, and KIS credentials.

저장소 최상위에서 API 없이 합성 예제를 실행할 수 있습니다.

Run the synthetic example from the repository root without connecting to an API.

```bash
python -m pip install -r stock_ff5/requirements.txt
python -m stock_ff5 demo --out stock_ff5/data/demo
python -m stock_ff5 signal --data stock_ff5/data/demo --as-of 2026-01-16 --out stock_ff5/output/demo-signal.json
python -m stock_ff5 backtest --data stock_ff5/data/demo --out stock_ff5/output/demo-backtest.csv
```

`demo`의 출력 경로는 비어 있어야 합니다. 합성 예제는 실제 투자성과가 아닙니다.
주문 기본 환경은 모의투자이며, 주문 전송에는 별도 실행 옵션이 필요합니다.
자세한 데이터 형식, 주문 조건, 검증 범위는 [설명서](stock_ff5/README.md)를 참고하세요.

The `demo` output directory must be empty. Synthetic results are not actual investment performance. The default order environment is paper trading; submitting orders requires additional command-line options. See the [guide](stock_ff5/README.md) for data formats, order conditions, and validation coverage.

## 기존 Quant 노트북 / Legacy quant notebooks

| 노트북 / Notebook | 한국어 설명 | English description |
| --- | --- | --- |
| [EMAcross.ipynb](Quant_models/EMAcross.ipynb) | Finter 기반 50/200일 EMA 신호 및 시뮬레이션 | Finter-based 50/200-day EMA signals and simulation |
| [fibonacci.ipynb](Quant_models/fibonacci.ipynb) | Finter 기반 피보나치 되돌림 신호 및 시뮬레이션 | Finter-based Fibonacci retracement signals and simulation |
| [fama_french.ipynb](Quant_models/fama_french.ipynb) | 암호화폐용 대체 팩터·기술적 지표·백테스트 실습 | Cryptocurrency proxy factors, technical indicators, and backtesting exercises |
| [autotrading_korbit.ipynb](Quant_models/autotrading_korbit.ipynb) | Korbit API와 이동평균 기반 자동거래 실습 | Korbit API integration and moving-average automated trading exercises |

노트북은 Python 3 기반 Jupyter 또는 Google Colab에서 열 수 있습니다.
패키지는 각 노트북의 설치 셀에 기재되어 있습니다.

Open the notebooks in Python 3 Jupyter Notebook or Google Colab. Required packages are listed in each notebook's installation cell.

- EMA·Fibonacci 노트북은 Finter 데이터 접근 권한과 `FINTER_API_KEY` 환경변수가 필요합니다.
- 가상화폐 Fama–French 노트북은 변동성·평균회귀 등을 대체 팩터로 쓰는 실습이며, 표준 주식 5요인 모델과 구분됩니다. Korbit 인증 설정은 `KORBIT_API_KEY`, `KORBIT_API_SECRET` 환경변수에서 읽습니다.
- Korbit 자동거래 노트북은 `getpass`로 인증정보를 입력받으며 실제 주문 코드가 포함되어 있습니다.

- The EMA and Fibonacci notebooks require access to Finter data and the `FINTER_API_KEY` environment variable.
- The cryptocurrency Fama–French notebook is an exercise using proxies such as volatility and mean reversion, rather than the standard equity five-factor model. It reads Korbit credentials from `KORBIT_API_KEY` and `KORBIT_API_SECRET`.
- The Korbit automated trading notebook prompts for credentials using `getpass` and includes code that can place actual orders.

기존 노트북의 현재 API 호환성과 실제 거래 실행은 검증하지 않았습니다.
인증정보는 코드·노트북 출력·Git에 저장하지 마세요.

Compatibility with current APIs and actual trade execution have not been verified for the legacy notebooks. Do not store credentials in code, notebook outputs, or Git.

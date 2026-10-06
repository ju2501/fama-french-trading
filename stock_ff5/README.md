# Korean Stock Fama–French Five-Factor Trading

한국 주식용 **Fama–French 5요인 분석 + 월별 리밸런싱 + 한국투자증권(KIS) 주문** 코드입니다.
기존 `Quant_models`의 가상화폐 실습과 독립된 폴더입니다.

기본 주문 환경은 **모의투자(paper)**이며 `--submit`이 없으면 주문 계획만 저장합니다.
합성 데이터로 회귀·백테스트를 바로 실행할 수 있습니다. 증권사 연동에는 사용자가 준비한
한국 시장 데이터와 본인의 KIS 인증정보가 필요합니다. 실제 계좌에 연결해 검증한 코드는 아닙니다.

## 1. 모델과 매매 규칙

월별 초과수익률 회귀:

```text
R_i,t − RF_t = alpha_i + beta_MKT × MKT_RF_t
                      + beta_SMB × SMB_t + beta_HML × HML_t
                      + beta_RMW × RMW_t + beta_CMA × CMA_t + error_i,t
```

| 요인 | 의미 |
|---|---|
| MKT_RF | 시장 수익률 − 무위험 수익률 |
| SMB | 소형주 − 대형주 |
| HML | 높은 장부가/시가 비율 − 낮은 장부가/시가 비율 |
| RMW | 높은 영업수익성 − 낮은 영업수익성 |
| CMA | 낮은 자산 증가율 − 높은 자산 증가율 |

- 최근 60개월 중 최소 36개월의 공개된 관측치로 절편을 포함한 OLS 회귀를 합니다.
- `beta × 같은 학습 기간의 평균 요인 수익률`을 다음 달 초과수익률의 단순 추정치로 사용합니다.
  추정 alpha는 진단값으로만 저장하며 예측값에 더하지 않습니다.
- 추정 초과수익률이 양수인 상위 5개 종목을 균등 배분합니다. 종목당 최대 20%, 전체 최대 90%이며
  남는 비중은 현금으로 둡니다. 공매도와 신용거래는 구현하지 않습니다.
- 이는 FF5 자산가격모형에 별도로 붙인 **실험적 종목선정 규칙**입니다. FF5 자체가 매매 시점이나
  미래 수익을 보장하지 않으며, 높은 기대수익 추정은 높은 위험노출을 의미할 수도 있습니다.
- `available_on < 의사결정일`인 요인만 사용합니다. 공개일에 시각 정보가 없어서 그 당일도 제외합니다.
  미래 값을 채워 넣거나 전체 기간으로 회귀한 뒤 과거에 적용하지 않습니다.

기존 암호화폐 노트북의 변동성·평균회귀 대용값을 SMB/HML로 사용하지 않습니다.
미국 FF5나 아시아 지역 FF5를 한국 개별주식 요인으로 자동 대입하지도 않습니다.

## 2. 설치 및 API 없이 실행하기

모든 명령은 **저장소 최상위 폴더**에서 실행합니다. Python 3.10 이상이 필요합니다.

```bash
python -m pip install -r stock_ff5/requirements.txt
python -m stock_ff5 demo --out stock_ff5/data/demo
python -m stock_ff5 signal --data stock_ff5/data/demo --as-of 2026-01-16 --out stock_ff5/output/demo-signal.json
python -m stock_ff5 backtest --data stock_ff5/data/demo --out stock_ff5/output/demo-backtest.csv
python -m unittest discover -s stock_ff5/tests -v
```

`demo`는 2016–2025년의 **합성** 월별 데이터를 생성합니다. 종목코드도 가상이며 실제 투자성과가 아닙니다.
기존 데이터를 덮어쓰지 않도록 비어 있는 경로에만 생성합니다. 합성 데이터는 증권사 주문 경로에서 거부됩니다.

## 3. 한국 시장 데이터 준비

`stock_ff5/data/kr/`에 다음 네 파일을 준비합니다. 실제 데이터는 저장소에 포함하지 않습니다.
이 모듈은 KRX·재무제표 수집기나 유료 데이터 서비스의 대체물이 아닙니다.

### metadata.json

```json
{
  "market": "KR",
  "currency": "KRW",
  "frequency": "monthly",
  "units": "decimal",
  "synthetic": false,
  "factor_source": "실제 한국 5요인 데이터 공급자 또는 자체 구축 방식과 출처",
  "vintage_note": "당시 공개본/수정 이력 및 산출일 관리 방식"
}
```

`synthetic=false`는 실제 데이터를 준비한 경우에만 사용하세요. 메타데이터는 출처를 자동 인증하지 않습니다.

### factors.csv

```csv
date,available_on,MKT_RF,SMB,HML,RMW,CMA,RF
2025-01-31,2025-02-15,0.025,0.006,-0.004,0.003,0.002,0.002
```

- 위 한 줄은 **형식 예시**입니다. 실제 값이 아닙니다. 최소 36개월 이상의 연속 월 자료가 필요합니다.
- `date`: 수익률 대상 월의 달력상 말일. `available_on`: 해당 관측치가 실제로 사용 가능해진 날짜.
- 모든 수익률은 **월별 소수 단위**입니다. 1%는 `0.01`이며 연율 무위험금리를 그대로 넣지 않습니다.
- KRW 주식 총수익률과 일관된 한국 시장 요인·KRW 무위험 수익률을 사용하세요.
- 수정된 최신 자료에 과거 공개일을 붙이면 look-ahead bias가 다시 생깁니다. 과거 백테스트는
  당시 공개본을 사용해야 하며, 코드가 데이터 제공자의 수정 이력을 복원하지는 않습니다.
- 부재 월, NaN, 무한대, 큰 결측치 표시값은 거부합니다. `2.5`처럼 명백한 퍼센트 입력도 거부하지만
  `0.5`가 의도한 50%인지 잘못 입력한 0.5%인지는 자동 판별할 수 없습니다.

### returns.csv

```csv
date,005930,000660
2025-01-31,0.03,-0.02
```

월별 **배당·분할·상장폐지 등을 반영한 총수익률**을 입력합니다. 숫자형 가격이 아니라 수익률입니다.
모든 날짜는 달력상 월말로 정규화하고, 누락 수익률을 0으로 채우지 마세요.
매매 가능한 종목은 6자리 KRX 주식 코드로 제한합니다. ETN·해외주식은 지원하지 않습니다.
학습 이력이 부족한 종목은 제외하고, 백테스트 보유 종목의 수익률이 누락되면 중단합니다.

### universe.csv

```csv
symbol,start,end
005930,2016-01-01,
000660,2016-01-01,
```

매 시점 실제로 투자대상이었던 종목과 편입·편출 날짜를 관리합니다. `end` 공란은 계속 유효함을 뜻합니다.
현재 상장 종목만 과거 전체 기간에 적용하면 생존편향이 생깁니다. 현재 구현은 종목당 한 편입 구간을 받습니다.
위 종목들은 형식 설명용이며 추천 목록이 아닙니다.

### 이미 2×3 포트폴리오 수익률을 갖고 있다면

```bash
python -m stock_ff5 build-factors --portfolios stock_ff5/data/kr/portfolios.csv --out stock_ff5/data/kr/factors.csv
```

입력 열은 `date,available_on,market_return,RF`와 아래 18개입니다.

| 정렬 기준 | 포트폴리오 열 |
|---|---|
| 장부가/시가 | value_SL, value_SN, value_SH, value_BL, value_BN, value_BH |
| 영업수익성 | profit_SL, profit_SN, profit_SH, profit_BL, profit_BN, profit_BH |
| 투자(자산 증가율) | invest_SL, invest_SN, invest_SH, invest_BL, invest_BN, invest_BH |

`S/B`는 소형/대형, `L/N/H`는 각 지표의 낮음/중립/높음입니다. 입력은 미리 구성한
**시가총액 가중 포트폴리오의 월별 수익률**이어야 합니다. 이 명령은 개별 기업의 재무제표로
포트폴리오를 생성하지 않고, 세 가지 SMB를 평균하고 HML/RMW/CMA의 long–short 수익률을 결합합니다.
국내 표본, 기준시장, 분할점, 연간 재구성, 재무제표 공개 지연, 가중치 시차는 데이터 구축 단계에서
명시해야 합니다. 국제 원 논문의 요인을 정확히 복제했다고 가정하지 마세요.

## 4. 백테스트

```bash
python -m stock_ff5 backtest --data stock_ff5/data/kr --out stock_ff5/output/kr-backtest.csv --cost-bps 20 --sell-tax-bps 0
```

매월 초 의사결정 → 그 달 수익률 적용 순서입니다. 리밸런싱 직전 비중은 이전 달 수익률에 따른
비중 변화를 반영합니다. 매수·매도 회전율에 비용을 부과하며 매도세율은 별도 설정합니다.
기본 `20bp`는 예시 비용 가정, `0bp` 세금은 **현행 한국 세율이라는 뜻이 아닙니다**.
계좌·시장·시점에 맞는 비용과 세율을 입력하세요.

출력은 월별 NAV, 수익률, 회전율, 비용, 목표 현금비중입니다.
이 백테스트는 전월말 가격에서 소수 단위 비중을 즉시 맞춘다고 가정하는 연구용 근사입니다.
시초가 갭, 호가·거래정지·상하한가, 정수 주수, 주문 미체결·부분체결을 재현하지 않습니다.
현금 이자는 0으로 가정하므로 RF는 주식 초과수익률 회귀에만 사용됩니다.

## 5. 한국투자증권 모의매매

한국투자증권 Open API에서 **모의투자용 앱키·앱시크릿·계좌**를 준비하고,
`.env.example`에 적힌 이름으로 환경변수를 설정합니다. `.env` 파일을 자동으로 읽지는 않습니다.
실제 값은 코드나 Git에 넣지 마세요.

```text
KIS_ENV=paper
KIS_APP_KEY=<모의투자 앱키>
KIS_APP_SECRET=<모의투자 앱시크릿>
KIS_CANO=<계좌 앞 8자리>
KIS_ACNT_PRDT_CD=<계좌 뒤 2자리>
```

먼저 주문 전송 없이 잔고·시세·매수가능금액을 조회하고 계획만 저장합니다.

```bash
python -m stock_ff5 rebalance --data stock_ff5/data/kr --budget 5000000 --max-order-value 1000000 --out stock_ff5/output/paper-plan.json
```

실제 KRX 거래일이 기재된 `sessions.csv`를 준비합니다. 열 이름은 `date`, 값은 `YYYY-MM-DD`입니다.
공휴일을 포함한 단순 평일 목록을 사용하지 말고, 거래소 일정에 맞게 갱신하세요.
모의 계좌에 주문을 전송할 때만 `--submit`을 추가합니다.

```bash
python -m stock_ff5 rebalance --data stock_ff5/data/kr --budget 5000000 --max-order-value 1000000 --sessions stock_ff5/data/kr/sessions.csv --out stock_ff5/output/paper-orders.json --submit
```

- 현재 날짜 기준으로 신호를 다시 계산하고, 요인 수익률 대상 월이 100일보다 오래되면 중단합니다.
- KST 09:10–15:10 및 제공된 거래일 목록 안에서만 주문을 전송합니다.
  특별 개장시간·시장 중단을 실시간 판별하지는 않습니다.
- 전략 전용 계좌를 사용하세요. 데이터셋 종목 목록 외 보유자산이나 당일 KRX 미체결 주문이 있으면 중단합니다.
  같은 종목을 다른 전략이 함께 보유하는 경우 소유권을 구분할 수 없습니다.
- 정수 주수, 종목별 목표 비중, 계좌 평가액과 `--budget` 중 작은 금액을 기준으로 계획합니다.
  `--max-order-value`로 주문별 금액을 제한합니다.
- 미수 없는 매수가능금액·수량, 매도가능수량을 확인합니다. 매도대금의 체결을 미리 가정하지 않습니다.
  현금이 부족하거나 주문금액 상한에 걸리면 실제 보유비중은 목표에 못 미칠 수 있습니다.
- KRX **현재가 스냅샷의 지정가**로 매도부터 전송합니다. 가격 변동 시 미체결될 수 있으며
  자동 가격 추적·정정·취소·미체결 재주문 기능은 없습니다.
- 주문번호는 접수 확인이지 체결 완료가 아닙니다. 증권사 화면에서 체결·거절·부분체결을 확인하세요.

## 6. 반복 실행, 주문 기록, 실전 전환

월별 전략이므로 거래일 장중에 외부 작업 스케줄러로 `rebalance`를 호출할 수 있습니다.
이 저장소는 스케줄러를 설치하거나 실행 중인 서비스를 생성하지 않습니다.
실제 데이터 갱신과 환경변수 설정 후, 모의계좌에서 먼저 수동으로 전체 흐름을 점검하세요.

계좌·환경·달력 월 조합을 `stock_ff5/.state/`에 **주문 전** 기록합니다.
동일 월 재실행은 새 주문을 내지 않고 중단합니다. 파라미터나 목표비중을 바꿔도 같은 월 기록을 사용합니다.
한 달에 한 번만 주문 배치를 시도하며, 빈 계획도 해당 월을 처리한 것으로 기록합니다.

요청 시간초과 후 실제 주문 접수 여부가 불명확하면 기록에 남기고 중단합니다.
**기록 파일을 지워 무조건 재시도하지 마세요.** 계좌 주문·체결과 기록을 대조한 후 수동으로 처리해야 합니다.
자동 복구·체결 추적이 없으므로 무인 실전 운영용 완성 시스템으로 간주하지 마세요.
여러 서버에서 실행하면 기록이 공유되지 않습니다. 하나의 실행 호스트와 동일한 영속 상태 경로를 사용하세요.
API 토큰도 이 경로에 저장되고 만료 전에 재사용됩니다. 해당 폴더는 Git에서 제외됩니다.

실전 연결 코드는 포함되어 있지만 이 작업에서는 실전·모의 API 호출 및 주문을 실행하지 않았습니다.
실전에는 별도 실전 인증정보와 `KIS_ENV=live`, 그리고 **`--submit --allow-live` 두 옵션**이 필요합니다.
모의 검증, 체결 대조, 계좌별 비용·권한·API 호환성 확인 후에만 사용하세요.

## 파일과 검증

| 파일 | 역할 |
|---|---|
| `model.py` | 데이터 검증, FF5 회귀·선정, 월별 백테스트, 요인 조합 |
| `kis.py` | KIS 인증·잔고·시세·미체결·주문 API, 주문 계획과 영속 기록 |
| `__main__.py` | 명령행 실행과 주문 전 조건 확인 |
| `demo.py` | 재현 가능한 합성 예제 생성 |
| `tests/` | 모형·공개일·비용·주문 제한·API 응답·중복 방지 단위 테스트 |

테스트는 합성 데이터와 가짜 API 응답으로 실행하며 실제 네트워크나 계좌를 사용하지 않습니다.

## 출처 및 저장소 이름

2026-10-06 기준 공식 문서·예제의 인터페이스를 확인했습니다.

- [Fama–French 5요인 정의](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_5_factors_2x3.html)
- [KIS 공식 현금주문 예제](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/order_cash/order_cash.py)
- [KIS 잔고조회](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_balance/inquire_balance.py)
- [KIS 미수 없는 매수가능금액·수량](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_psbl_order/inquire_psbl_order.py)
- [KIS 일별 주문체결조회](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_daily_ccld/inquire_daily_ccld.py)

가상화폐 실습과 주식 FF5를 함께 두는 저장소 이름으로 `fama-french-trading`을 제안합니다.
GitHub `Settings → General → Repository name → Rename`에서 변경할 수 있습니다.
폴더와 문서의 내부 경로는 저장소 이름에 의존하지 않습니다.

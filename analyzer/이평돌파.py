# -*- coding: utf-8 -*-
""" 이평돌파 — 가격 5초 이평이 30초 이평을 상향 돌파하면 사고 하향 돌파하면 파는 초 단위 스캘핑 (분석 전용, 실매매 미연결)

    발상 (2026-11-02 사용자 정의)
      가격 5초 이평이 30초 이평을 위로 뚫으면 짧은 상승이 시작된 것으로 보고 사고, 아래로 뚫으면 판다.
      거짓 돌파는 체결횟수와 체결강도로 거른다.

    조건 (모두 신호 초 종료 시점까지의 정보, 이평은 '거래 시간' 축 - 거래 정지 구간·첫 체결 전을 빼고 이어 계산)
      ① 가격 이평 돌파   가격5 > 가격30 (가격5·가격30 = 1초 종가의 5초 / 30초 이동평균, v5 부터 짝은 칸마다 LI_이평 중 하나)
                          상향 돌파(직전 거래 초엔 가격5 ≤ 가격30)로 시작된 '위 구간' 안에서만 진입, 구간마다 1번
                          v2: 돌파한 초부터 N_돌파창 초 이내(거래 시간)에만 진입
                          v4: 1초 종가 ≥ 돌파 초 종가 + N_돌파호가 호가 (호가 단위는 돌파 초 종가 기준)
      ② 체결횟수         체결횟수(초당, 1·2주 단주 제외) 5초 이평 ≥ N_체결횟수5 그리고 5초 이평 > 30초 이평 (v3, v1 은 문턱만 · v2 는 5초 > 30초만)
      ④ 직전 60초 고저폭 (v6) 직전 60초(시계, 그 초 포함) 최고가 ÷ 최저가 − 1 ≥ N%
      ⑤ 제외 조건 (v9)    체결횟수 5초 이평 ÷ 30초 이평 ≥ 3 · 체결횟수 30초 이평 ÷ 직전 5분 평균 ≥ 3 · 평소 가격변동 < 20% 이면 사지 않음
      ⑥ 당일 누적 거래대금 (v12) 진입 초까지 누적 거래대금 < N억
      ⑦ 분봉 3분 수익률 (v12) 진입 분 바로 앞 완결 시계 분봉 종가 ÷ 그 3분 전 분봉 종가 − 1 > N%
                          (①~④ 가 처음 모두 켜진 초에 걸리면 그 위 구간은 건너뜀 - 조건이 풀리는 뒤 초로 미뤄 사지 않는다)
      ③ 체결강도         5초 체결강도 = 직전 5초 매수량 ÷ 매도량 × 100 ≥ N_체결강도5 (단주 제외, 매도 0 이면 999)
      공통               09:01 ~ 15:10 진입 · 가격 1,000원 이상 · 거래 정지가 풀린 뒤 10초 동안 진입 안 함
      청산               가격5 ≤ 가격30 이 되는 첫 거래 초 (하향 돌파, 진입에 쓴 이평 짝) · 15:15 강제 청산
                          v8: 손절 - 1초 저가 ≤ 매수가 × (1 − N%) 인 첫 초에 min(손절선, 그 초 종가) 로 판다 (같은 초 하향 돌파보다 먼저)
                          v11: 대기 - 하향 돌파 초의 종가가 매수가 −기준% 보다 위면 바로 팔지 않고 N초 기다린다
                               그 사이 다시 위로 올라오면 계속 보유 · 1초 저가가 매수가 −기준% 에 닿으면 그 초에 판다 · N초가 지나도 아래면 그때 판다

    체결 가정 (2026-10-30 실매매 400건 실측)
      매수 = 신호 초 종가 × (1 + 0.14%) · 매도 = 청산 초 종가 × (1 − 0.05%) · 세금·수수료 0.3% 고정 → 왕복 약 0.49%
      '비용 전' = 청산 초 종가 ÷ 신호 초 종가 − 1 (방향성만 본다)

    검증
      일자를 무작위로 반씩 나눠(씨앗 N_분할씨앗) IS·OOS 를 따로 보여 준다. 기준 규칙은 사전에 고정했으므로 IS 에서 고르지 않는다.
      S_봉인시작 부터의 날짜(2026-10-30 ~, 전진검증용으로 남겨 둔 날)는 쓰지 않는다.
      통과 문턱 (2026-10-30 수익 구멍 점검): 비용 전 ≥ +0.7%, 실측 순수익 ≥ +0.2% 를 IS·OOS 양쪽에서

    1초 캐시 ({work}/분석/백테스팅/이평돌파/_초캐시, 틱에서 다시 만들 수 있다)
      초2_YYYYMMDD.npz  종목×초×12 - 0 종가(ffill) 1 고가 2 저가(체결 없으면 nan) 3 매수량 4 매도량(단주 제외) 5 체결건수(단주 제외)
                        6 누적거래대금(백만원) 7 전일종가 8 시가 9 매수건수 10 매도건수 11 체결건수(전체)
      초량_YYYYMMDD.npz 종목×초 체결량 (1·2주 단주 포함 전체, 주)
      호가_YYYYMMDD.npz 종목×초×6 - 매도·매수호가 총잔량 · 1호가 수량 · 1~3호가 수량 합 (호가 csv 가 있는 날만, 2026-10-12 ~)
      (관성매매와 같은 형식 - 2026-11-02 관성매매 캐시를 복사해 시작했다)

    버전 기록
      v1 (2026-11-02) 사용자 규칙 - ① 상향 돌파 위 구간 · ② 체결횟수 5초 이평 ≥ 5 · ③ 5초 체결강도 ≥ 100 · 청산 하향 돌파
                       비교 칸: 돌파 초에 ②③ 이 함께 켜져야 진입 / ②③ 없이 돌파만
                       → 비용 전 IS −0.035·OOS −0.033 (이익일 0/31), 돌파만 −0.09 - 기각
      v2 (2026-11-02) 사용자 규칙 - ② 체결횟수 문턱 5 → 5초 이평 > 30초 이평 · ① 상향 돌파 후 5초 이내에만 진입 (③ 체결강도 그대로)
                       비교 칸: 5초 창 없음(② 만 바꿈) / v1 기준 / 돌파만
                       → 문턱이 빠져 하루 2.4만 건 (v1 의 35배), 비용 전 IS −0.080·OOS −0.082 - 잔물결 돌파가 다 들어와 v1 보다 나쁨, 기각 (리포트 없음)
      v3 (2026-11-02) 사용자 규칙 - ② 체결횟수 5초 이평 ≥ 5 문턱을 되살리고 5초 이평 > 30초 이평도 함께 · ① 돌파 후 5초 이내 · ③ 그대로
                       비교 칸: ② 문턱만(5초 > 30초 없음) / v1 기준 / 돌파만
                       → 비용 전 IS −0.055·OOS −0.049 (v1 −0.035/−0.033 보다 나쁨, 5초 창·5초 > 30초 모두 조금씩 악화) - 기각
      v4 (2026-11-02) 사용자 규칙 - v3 + ① 돌파 초 종가보다 3호가 이상 오른 초에만 진입
                       비교 칸: v3 기준(3호가 없음) / 3호가 · 5초 창 없음 / v1 기준
                       → 비용 전 기준 IS −0.023·OOS −0.045 · 3호가·창 없음 −0.017/−0.023 (v1~v4 최선, 여전히 음수) - 기각
      v5 (2026-11-02) 3호가·창 없음을 기본으로 격자 - 돌파 호가 3/5/7 × 가격 이평 짝 5/30·10/60·20/120 (청산도 같은 짝의 하향 돌파) = 9칸 + v1 비교
                       기준(그래프·그룹 분석) = 3호가 · 5/30 (사전 고정)
                       → 호가가 많을수록·이평이 짧을수록 낫다. 최선 7호가 · 5/30 비용 전 IS +0.031·OOS +0.006 (일 단위 95% 가 0 걸침, 실측 −0.46/−0.48,
                         이익일 0/31, 상위 1% 빼면 −0.05/−0.07) · 10/60 은 −0.01~−0.07, 20/120 은 −0.03~−0.14 - 통과 문턱 +0.7 과 거리가 커 기각
      v6 (2026-11-02) ④ 직전 60초 고저폭 ≥ N% 격자 (둥근 값 0/1/2/3/4, 0 = 조건 없음) × 돌파 호가 3/5/7 · 이평 5/30 만 = 15칸 + v1 비교
                       (v5 수익·손실 분석: 60초 고저폭이 ±1% 밖 거래를 가장 잘 가름 - 상위 20% 경계 2.8% 는 결과를 보고 잡은 값이라 둥근 격자로)
                       리포트에 '애매한 거래'(비용 전 ±1% 안) 비율과 ±1% 밖 거래의 + / − 구성 · 기준 = 7호가 · 고저폭 3% (사전 고정)
                       → 고저폭을 올릴수록 애매한 거래 82% → 50% 로 줄지만 − 쪽도 같이 늘어 OOS 는 3% 에서 정점 (7호가 IS +0.178·OOS +0.062, 일 단위 구간 0 걸침),
                         4% 는 IS +0.25·OOS +0.03 로 엇갈림 - IS 개선은 OOS 에서 1/3 만 남음, 통과 문턱 +0.7 미달
      v7 (2026-11-02) ④ 60초 고저폭 3% 고정 (격자에서 뺌) → 돌파 호가 3/5/7 = 3칸 + v1 비교 (결과 = v6 의 고저폭 3% 칸, 아직 다시 돌리지 않음)
      v8 (2026-11-02) 청산에 손절 추가 (하향 돌파는 유지) - 손절 없음 / 0.5 / 1 / 1.5 / 2 / 3% × 돌파 호가 3/5/7 = 18칸 + v1 비교
                       기준(그래프·그룹 분석) = 7호가 · 손절 1% (사전 고정) · 리포트에 손절로 끊은 거래의 '손절 없었으면' 짝 비교
                       → 모든 손절 폭이 IS·OOS 모두 거래당을 깎음 (7호가 OOS 비용 전 없음 +0.062 · 0.5% −0.096 · 1% −0.056 · 1.5% −0.026 · 2% −0.002 · 3% +0.046)
                         하향 돌파 청산(보유 중앙 25초)이 이미 손실을 짧게 끊고 있어, 손절은 흔들림에 걸려 나갔다가 회복할 거래(10~23%)까지 끊는다 - 기각
      v9 (2026-11-02) 손절 없음 (v7 로 되돌림) + ⑤ v5 수익·손실 분석의 제외 조건 셋을 둥근 값으로 - 없음 / 체결횟수비 / 체결횟수배수 / 평소변동 / 3종 모두
                       × 돌파 호가 3/5/7 = 15칸 + v1 비교 · 기준(그래프·그룹 분석) = 7호가 · 3종 모두 (사전 고정)
                       (제외 조건은 v5 의 IS·OOS 를 다 보고 고른 것이라 이번 OOS 도 이미 본 데이터 - 독립 확인은 봉인 날짜로)
                       → 고저폭 3% 위에서는 체결횟수비만 IS·OOS 둘 다 나쁜 거래를 뺌 (빠진 거래 IS −0.08·OOS −0.07, 7호가 IS +0.178→+0.221·OOS +0.062→+0.089)
                         체결횟수배수·평소변동은 IS 에선 좋은 거래(+0.18~0.19)를 빼고 OOS 에선 나쁜 거래를 빼 엇갈림 (고저폭 3% 가 이미 겹치는 정보)
                         3종 모두 IS +0.165·OOS +0.100 (IS 는 오히려 나빠짐) - 일관된 것은 체결횟수비 하나, 통과 문턱 +0.7 미달
      v10 (2026-11-02) ⑤ 제외 조건을 체결횟수비(5초 ÷ 30초 이평 ≥ 3) 하나로 고정 → 돌파 호가 3/5/7 = 3칸 + v1 비교
                       (결과 = v9 의 체결횟수비 칸, 아직 다시 돌리지 않음 · 7호가 비용 전 IS +0.221·OOS +0.089) - 다음 확인은 봉인 날짜(10/30 ~)로
      v11 (2026-11-02) 청산 대기 (사용자 규칙) - 하향 돌파 때 손실이 기준보다 얕으면 N초 기다림 · 기준 0.5/1/1.5/2% × 대기 3/5/10/20초 + 대기 없음
                       = 17칸 (7호가만 - v6~v9 에서 3/5/7 호가 차이가 작다) + v1 비교 · 기준(그래프·그룹 분석) = 대기 5초 · 기준 1% (사전 고정)
                       → IS 는 16칸 모두 대기 없음(+0.221)보다 나쁨 (3초 +0.17~0.19 · 20초 +0.06~0.10), OOS 는 3·5초 · 기준 1~2% 만 +0.01~0.04%p 낫고
                         10·20초는 나쁨 - IS·OOS 엇갈림. 대기로 청산이 바뀐 거래 중 나아진 건 21~41% (하향 돌파 뒤 대개 더 내려간다) - 기각
      ※ v11 기각 → v10 설정으로 롤백 (S_버전 v10 · 대기 없음 · 대기청산·대기짝·리포트 대기 표는 선택지로 남김)
      v12 (2026-11-02) v10 + ⑥ 당일 누적 거래대금 < 없음/50/100/200억 × ⑦ 분봉 3분 수익률 > 없음/0/1% = 12칸 (7호가만) + v1 비교
                       (v10 거래 2,161건의 초·분봉·전일 분봉·20일 일봉 80개 항목 비교에서 거래당을 IS·OOS 둘 다 가른 두 항목 - 문턱은 둥근 값)
                       리포트에 칸별 시간대(09:01~09:10 / 09:10~10시 / 10~12시 / 12시~15:10) 비용 전 거래당 · 기준 = 100억 · 0% (사전 고정)
                       → ⑥ 누적 대금은 IS·OOS 둘 다 개선 (100억 IS +0.274·OOS +0.156 · 200억 +0.249/+0.152, v10 +0.221/+0.089)
                         ⑦ 3분 수익은 IS 만 개선·OOS 는 그대로거나 나빠짐 (조건 없음 +0.089 → 0% +0.067 · 50억+0% IS +0.51·OOS +0.03) - 기각
                         시간대: 09:01~10시는 IS·OOS 둘 다 +0.1~0.3, 10~12시는 모든 칸에서 IS + · OOS − 로 엇갈림 · 통과 문턱 +0.7 미달
      v13 (2026-11-02) ⑥ 당일 누적 거래대금 < 100억 고정 · ⑦ 분봉 3분 수익 조건 없음 → 1칸 (7호가) + v1 비교
                       (결과 = v12 의 100억 · 조건 없음 칸, 아직 다시 돌리지 않음 · 비용 전 IS +0.274·OOS +0.156, 하루 21~23건) - 다음 확인은 봉인 날짜(10/30 ~)로

    사용
        python analyzer/이평돌파.py --cache    # 새 틱 일자 1초 캐시만 생성
        python analyzer/이평돌파.py            # 빠진 캐시 보충 → 칸 실행 → 리포트 저장 → 텔레그램
        python analyzer/이평돌파.py --proc 2   # 장중에는 병렬 프로세스를 줄인다
"""
import os
import io
import sys
import json
import math
import base64
import random
import argparse
import datetime
import urllib.parse
import warnings
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ut

# ===== 버전·검증 설정 =====
S_버전 = 'v13'
N_분할씨앗 = 20261102                 # 일자 무작위 분할 씨앗 - 바꾸면 IS/OOS 가 바뀌므로 버전과 함께 기록
LI_제외일 = ['20260817', '20260924', '20260925']   # 임시공휴일 · 추석 연휴 (틱 없음)
S_봉인시작 = '20261030'               # 이 날짜부터는 전진검증용으로 남겨 둔다 (격자에 쓰지 않음)
S_리포트폴더 = '클로드분석결과'        # 서버 웹폴더(server_kakao) 하위

# ===== 시간·체결 =====
T0 = 9 * 3600
N_초 = 6 * 3600 + 30 * 60 + 1          # 09:00:00 ~ 15:30:00
S_마감 = 15 * 3600 + 15 * 60 - T0      # 15:15 강제 청산
N_단주 = 2                             # 1·2주 체결은 단주로 보고 체결횟수·체결강도에서 뺀다
# 실측 비용 (2026-10-30): 수수료·세금 0.3% 고정 + 실매매 400건 판정 완결 초 종가 → 체결 매수 0.14% · 매도 0.05%
N_실측비용, N_실측매수, N_실측매도 = 0.30, 0.14, 0.05
# 거래 정지 추정 - 틱에 정지 표시가 없어 '체결 없는 구간 N_정지최소초 이상 + 직전 30초 체결 N_정지직전건수 이상' 으로 본다
N_정지최소초, N_정지직전건수 = 60, 30
N_정지후금지 = 10                      # 거래 정지가 풀린 초부터 N초 동안 진입하지 않는다

# ===== 조건 (v1) =====
N_체결횟수5, N_체결강도5 = 5, 100      # 체결횟수 5초 이평 문턱 (v2 는 문턱을 빼 기각) · 5초 체결강도 문턱
N_돌파창 = 5                           # v2: 상향 돌파한 초부터 이 초 수 이내(거래 시간, 돌파 초 = 0)에만 진입
N_돌파호가 = 3                         # v4: 1초 종가가 돌파 초 종가보다 이 호가 수 이상 높을 때만 진입
DIC_공통 = dict(시작=60, 종료=S_마감 - 300, 가격min=1000)
LI_이평 = [(5, 30)]                         # 가격 이평 짝 (짧은 / 긴, 초) - 지표가 짝마다 위·돌파·경과·돌파가를 만든다 (v5 격자 10/60·20/120 은 일관되게 나빠 v6 에서 뺐다)
LI_호가 = [7]                                # 돌파 초 종가보다 N 호가 이상 - v5~v10 격자 3/5/7 은 차이가 작아 v11·v12 는 7호가만
LI_고저폭 = [3]                              # 직전 60초 고저폭 ≥ N% (0 = 조건 없음) - v6 격자 0/1/2/3/4 에서 OOS 정점인 3% 로 v7 부터 고정
LI_손절 = [0]                                # 매수가 대비 손절 % (0 = 손절 없음, 하향 돌파 청산은 그대로) - v8 격자 0.5/1/1.5/2/3% 가 모두 나빠 v9 에서 뺐다
N_횟수비상한, N_횟수배수상한, N_변동하한 = 3, 3, 20   # v9 ⑤ 제외 조건 (v5 분석 상·하위 20% 경계 2.8~3.3 · 약 3 · 19~24% 를 둥근 값으로)
DIC_제외 = {'없음': (), '횟수비': ('횟수비',), '횟수배수': ('횟수배수',), '변동': ('변동',), '3종': ('횟수비', '횟수배수', '변동')}
DIC_제외이름 = {'횟수비': f'체결횟수 5초 ÷ 30초 이평 ≥ {N_횟수비상한}', '횟수배수': f'체결횟수 30초 이평 ÷ 직전 5분 평균 ≥ {N_횟수배수상한}', '변동': f'평소 가격변동 < {N_변동하한}%'}
LI_대금 = [100]                              # ⑥ 진입 초까지 당일 누적 거래대금 < N억 (0 = 조건 없음) - v12 격자 없음/50/100/200 에서 IS·OOS 둘 다 나은 100억으로 v13 부터 고정
LI_분수익 = [None]                           # ⑦ 분봉 3분 수익률 > N% (None = 조건 없음) - v12 격자 0/1% 는 IS 만 좋아져 기각
LI_시간대 = [(60, 600, '09:01~09:10'), (600, 3600, '09:10~10시'), (3600, 3 * 3600, '10~12시'), (3 * 3600, S_마감, '12시~15:10')]   # v12 리포트 시간대별 표
LI_대기 = [(0, 0)]                           # (대기 초, 손실 기준 %) - (0, 0) = 대기 없음 · v11 격자 기준 0.5/1/1.5/2% × 대기 3/5/10/20초는 IS 에서 모두 나빠 기각
LI_제외 = ['횟수비']                         # ⑤ 제외 방식 - v9 격자(없음 / 하나씩 / 3종) 에서 IS·OOS 둘 다 나쁜 거래를 뺀 체결횟수비 하나로 v10 부터 고정
N_애매 = 1.0                                 # v6 리포트: 비용 전 |수익| < N% 를 '애매한 거래'로 센다
# 칸: 이평 = 가격 이평 짝 · 창 = 상향 돌파 후 진입을 허용하는 초 (None = 위 구간 전체, 0 = 돌파 그 초만)
#     횟수 = ② 방식 ('문턱이평위' 5초 ≥ N_체결횟수5 그리고 5초 > 30초 / '문턱' 5초 ≥ N_체결횟수5 / '이평위' 5초 > 30초 / None 조건 없음)
#     강도 = ③ 5초 체결강도 ≥ N_체결강도5 사용 여부 · 호가 = 돌파 초 종가보다 N 호가 이상 (0 = 조건 없음) - 각 위 구간에서 조건이 처음 모두 켜지는 초에 산다
#     (v4 까지 쓴 칸: v3 = 창 5·호가 0 / v4 기준 = 창 5·호가 3 / 돌파만 = 창 0·횟수 None·강도 False - v1~v3 비용 전 −0.094)
#     고저폭 = 직전 60초 고저폭 ≥ N% (0 = 조건 없음) · 손절 = 매수가 대비 손절 % (0 = 없음) · 제외 = DIC_제외 키 (⑤ 제외 조건 묶음)
def 대기이름(wk):
    return '대기 없음' if not wk[0] else f'대기 {wk[0]}초 · 기준 −{wk[1]:g}%'


def 행이름(g, sl, x, a, b, wk=(0, 0), u=0, r=None):
    """ 칸 이름에서 호가를 뺀 부분 - 값이 여럿인 축만 적는다 """
    return ' · '.join(([f'가격 {a}초/{b}초 이평'] if len(LI_이평) > 1 else []) + ([('고저폭 조건 없음' if g == 0 else f'고저폭 ≥ {g}%')] if len(LI_고저폭) > 1 else [])
                      + (['손절 없음' if not sl else f'손절 {sl:g}%'] if len(LI_손절) > 1 else [])
                      + ([{'없음': '제외 없음', '3종': '제외 3종 모두'}.get(x, '제외 ' + DIC_제외이름.get(x, x))] if len(LI_제외) > 1 else [])
                      + ([대기이름(wk)] if len(LI_대기) > 1 else [])
                      + ([('누적 대금 조건 없음' if not u else f'누적 대금 < {u}억')] if len(LI_대금) > 1 else [])
                      + ([('3분 수익 조건 없음' if r is None else f'3분 수익 > {r:g}%')] if len(LI_분수익) > 1 else [])) or '-'


LI_칸 = [dict(id=f'호가{h}|고저폭{g}|손절{sl:g}|제외{x}|대기{wk[0]}_{wk[1]:g}|대금{u}|분{"없음" if r is None else f"{r:g}"}|이평{a}_{b}',
              이름=f'+{h}호가' + ('' if 행이름(g, sl, x, a, b, wk, u, r) == '-' else ' · ' + 행이름(g, sl, x, a, b, wk, u, r)), 행=행이름(g, sl, x, a, b, wk, u, r),
              이평=(a, b), 창=None, 횟수='문턱이평위', 강도=True, 호가=h, 고저폭=g, 손절=sl, 제외=x, 대기=wk, 대금=u, 분수익=r)
        for (a, b) in LI_이평 for g in LI_고저폭 for sl in LI_손절 for x in LI_제외 for wk in LI_대기 for u in LI_대금 for r in LI_분수익 for h in LI_호가] \
    + [dict(id='v1', 이름=f'v1 기준 (5/30 · 호가·고저폭·제외·대금·분봉 조건 없음 · 손절·대기 없음 · 체결횟수 5초 ≥ {N_체결횟수5})', 이평=(5, 30), 창=None, 횟수='문턱', 강도=True,
            호가=0, 고저폭=0, 손절=0, 제외='없음', 대기=(0, 0), 대금=0, 분수익=None)]
S_기준 = '호가7|고저폭3|손절0|제외횟수비|대기0_0|대금100|분없음|이평5_30'   # 그래프·그룹 분석을 그리는 칸 (v10 + v13 누적 대금 < 100억)
N_문턱비용전, N_문턱실측 = 0.7, 0.2
N_병렬 = 6                            # 병렬 프로세스 수 (장중에는 --proc 로 줄여 틱 수집을 해치지 않게)


# =====================================================================
# 1초 캐시
# =====================================================================
def folder_이평():
    return os.path.join(ut.폴더manager.FolderManager().dic_폴더정보['분석|백테스팅'], '이평돌파')


def folder_캐시():
    return os.path.join(folder_이평(), '_초캐시')


def _num(s):
    return pd.to_numeric(s.str.replace('+', '', regex=False).str.replace('-', '', regex=False), errors='coerce')


def _초(df, s_열):
    t = df[s_열].str
    return (pd.to_numeric(t[:2], errors='coerce') * 3600 + pd.to_numeric(t[2:4], errors='coerce') * 60
            + pd.to_numeric(t[4:6], errors='coerce')) - T0


def 틱읽기(s_일자, cols):
    """ 그날 체결틱 csv - 본 감시종목(주식체결/) + 두 번째 계좌 추가 감시종목(주식체결추가/ - 있을 때만) """
    dic = ut.폴더manager.FolderManager().dic_폴더정보
    li = [os.path.join(dic['매수매도|주식체결'], f'주식체결_{s_일자}.csv'), os.path.join(dic['매수매도|주식체결추가'], f'주식체결추가_{s_일자}.csv')]
    return pd.concat([pd.read_csv(p_, encoding='cp949', usecols=cols, dtype=str, on_bad_lines='skip') for p_ in li if os.path.exists(p_)], ignore_index=True)


def build_캐시(s_일자):
    """ 틱 CSV → 종목×초×12 배열 (채널은 맨 위 설명) """
    path_out = os.path.join(folder_캐시(), f'초2_{s_일자}.npz')
    if os.path.exists(path_out):
        return s_일자, '있음'
    df = 틱읽기(s_일자, ['종목코드', '체결시간', '현재가', '등락율', '거래량', '누적거래대금', '시가'])
    df['p'] = _num(df['현재가']); df['v'] = pd.to_numeric(df['거래량'], errors='coerce')
    df['r'] = pd.to_numeric(df['등락율'], errors='coerce'); df['cv'] = pd.to_numeric(df['누적거래대금'], errors='coerce')
    df['o'] = _num(df['시가']); df['s'] = _초(df, '체결시간')
    df = df.dropna(subset=['p', 'v', 's'])
    df = df[(df['s'] >= 0) & (df['s'] < N_초) & (df['p'] > 0)]
    df['s'] = df['s'].astype(int); df['종목코드'] = df['종목코드'].str.strip()
    li_코드 = sorted(df['종목코드'].unique())
    arr = np.full((len(li_코드), N_초, 12), np.nan, dtype=np.float32)
    for i, (code, g) in enumerate(df.groupby('종목코드', sort=True)):
        a = arr[i]; gs = g.groupby('s')
        last = gs['p'].last()
        a[last.index, 0] = last.values; a[:, 0] = pd.Series(a[:, 0]).ffill().values
        a[last.index, 1] = gs['p'].max().values; a[last.index, 2] = gs['p'].min().values
        u = g[g['v'].abs() > N_단주]
        a[:, [3, 4, 5, 9, 10, 11]] = 0
        b = u[u['v'] > 0].groupby('s')['v'].sum(); a[b.index, 3] = b.values
        sl = -u[u['v'] < 0].groupby('s')['v'].sum(); a[sl.index, 4] = sl.values
        n = u.groupby('s').size(); a[n.index, 5] = n.values
        nb = g[g['v'] > 0].groupby('s').size(); a[nb.index, 9] = nb.values
        ns = g[g['v'] < 0].groupby('s').size(); a[ns.index, 10] = ns.values
        na = gs.size(); a[na.index, 11] = na.values
        cv = gs['cv'].last(); a[cv.index, 6] = cv.values; a[:, 6] = pd.Series(a[:, 6]).ffill().fillna(0).values
        g1 = g.dropna(subset=['r']); g1 = g1[g1['r'] > -100]
        a[:, 7] = float(np.median(g1['p'].values[:50] / (1 + g1['r'].values[:50] / 100))) if len(g1) else np.nan
        o = g['o'].dropna(); a[:, 8] = float(o.iloc[0]) if len(o) else np.nan
    os.makedirs(folder_캐시(), exist_ok=True)
    np.savez(path_out, arr=arr, codes=np.array(li_코드))
    return s_일자, len(li_코드)


def build_전량(s_일자):
    """ 틱 CSV → 종목×초 체결량 (1·2주 단주 포함 전체, 주) - 종목 순서는 같은 날 초2_ 와 같다 """
    path_out = os.path.join(folder_캐시(), f'초량_{s_일자}.npz')
    if os.path.exists(path_out):
        return s_일자, '있음'
    codes = np.load(os.path.join(folder_캐시(), f'초2_{s_일자}.npz'))['codes']
    df = 틱읽기(s_일자, ['종목코드', '체결시간', '현재가', '거래량'])
    df['p'] = _num(df['현재가']); df['v'] = pd.to_numeric(df['거래량'], errors='coerce').abs(); df['s'] = _초(df, '체결시간')
    df = df.dropna(subset=['p', 'v', 's'])
    df = df[(df['s'] >= 0) & (df['s'] < N_초) & (df['p'] > 0)]
    df['s'] = df['s'].astype(int); df['종목코드'] = df['종목코드'].str.strip()
    idx = {cd: k for k, cd in enumerate(codes)}
    arr = np.zeros((len(codes), N_초), dtype=np.float32)
    g = df[df['종목코드'].isin(idx)].groupby(['종목코드', 's'])['v'].sum()
    arr[[idx[c_] for c_ in g.index.get_level_values(0)], g.index.get_level_values(1).to_numpy()] = g.values
    np.savez(path_out, arr=arr, codes=np.array(codes))
    return s_일자, len(codes)


def build_호가(s_일자):
    """ 호가잔량 CSV → 종목×초×6 (매도·매수호가 총잔량 · 매도·매수 1호가 수량 · 매도·매수 1~3호가 수량 합, 그 초 마지막 값을 다음 갱신까지 이어 씀)
        종목 순서는 같은 날 초2_ 와 같다 · 호가 csv 가 없는 날(2026-10-12 수집 시작 전)은 만들지 않는다 → None """
    path_out = os.path.join(folder_캐시(), f'호가_{s_일자}.npz')
    if os.path.exists(path_out):
        return s_일자, '있음'
    folder = ut.폴더manager.FolderManager().dic_폴더정보['매수매도|주식호가']
    li = [p_ for p_ in (os.path.join(folder, f'주식호가_{s_일자}.csv'), os.path.join(folder, f'주식호가추가_{s_일자}.csv')) if os.path.exists(p_)]
    if not li:
        return s_일자, None
    codes = np.load(os.path.join(folder_캐시(), f'초2_{s_일자}.npz'))['codes']
    cols = ['종목코드', '호가시간', '매도호가총잔량', '매수호가총잔량'] + [f'{k}호가수량{i}' for k in ('매도', '매수') for i in (1, 2, 3)]
    df = pd.concat([pd.read_csv(p_, encoding='cp949', usecols=cols, dtype={'종목코드': str, '호가시간': str}, on_bad_lines='skip') for p_ in li], ignore_index=True)
    for k in ('매도', '매수'):
        df[f'{k}1'] = df[f'{k}호가수량1']; df[f'{k}3'] = df[[f'{k}호가수량{i}' for i in (1, 2, 3)]].sum(axis=1)
    df['s'] = _초(df, '호가시간')
    df = df.dropna(subset=['s'])
    df['s'] = df['s'].astype(int).clip(lower=0)               # 장 시작 전 동시호가 잔량은 09:00:00 첫 값으로
    df = df[df['s'] < N_초]; df['종목코드'] = df['종목코드'].str.strip()
    idx = {cd: k for k, cd in enumerate(codes)}
    arr = np.full((len(codes), N_초, 6), np.nan, dtype=np.float32)
    g = df[df['종목코드'].isin(idx)].groupby(['종목코드', 's'])[['매도호가총잔량', '매수호가총잔량', '매도1', '매수1', '매도3', '매수3']].last()
    arr[[idx[c_] for c_ in g.index.get_level_values(0)], g.index.get_level_values(1).to_numpy()] = g.values.astype(np.float32)
    for k in range(len(codes)):
        arr[k] = pd.DataFrame(arr[k]).ffill().values
    np.savez(path_out, arr=arr, codes=np.array(codes))
    return s_일자, len(codes)


def 캐시보충(n_proc=3):
    """ 틱은 있는데 1초 캐시가 없는 일자를 만든다 - 장이 끝나지 않은 오늘(15:40 전) · 틱이 빈 날(1MB 미만) · LI_제외일 은 건너뛴다 """
    folder_틱 = ut.폴더manager.FolderManager().dic_폴더정보['매수매도|주식체결']
    os.makedirs(folder_캐시(), exist_ok=True)
    now = datetime.datetime.now()
    s_오늘 = now.strftime('%Y%m%d') if now.hour * 100 + now.minute < 1540 else None
    li = []
    for f in sorted(os.listdir(folder_틱)):
        if not (f.startswith('주식체결_') and f.endswith('.csv')):
            continue
        s_일자 = f[5:13]
        if s_일자 in LI_제외일 or s_일자 == s_오늘 or os.path.getsize(os.path.join(folder_틱, f)) < 1e6:
            continue
        if not all(os.path.exists(os.path.join(folder_캐시(), f'{k}_{s_일자}.npz')) for k in ('초2', '초량')):
            li.append(s_일자)
    if li:
        print('1초 캐시 보충', li, flush=True)
        with Pool(n_proc) as pool:
            for r in pool.imap_unordered(build_캐시, li):
                print(r, flush=True)
            for r in pool.imap_unordered(build_전량, li):
                print(r, flush=True)
            for r in pool.imap_unordered(build_호가, li):
                print(r, flush=True)
    return li


def li_캐시일자():
    li = sorted(f[3:11] for f in os.listdir(folder_캐시()) if f.startswith('초2_') and f.endswith('.npz'))
    return [s for s in li if s not in LI_제외일 and s < S_봉인시작]


def 분할(li_일자):
    """ 일자 무작위 반반 분할 → (IS, OOS) """
    li = sorted(li_일자); r = random.Random(N_분할씨앗); s = li[:]; r.shuffle(s)
    return sorted(s[:len(s) // 2]), sorted(s[len(s) // 2:])


def 적재(s_일자):
    """ 12채널 + 채널 12 전체 체결량 + 채널 13~18 호가 (호가 csv 가 없는 날은 nan) → (배열, 종목코드) """
    z = np.load(os.path.join(folder_캐시(), f'초2_{s_일자}.npz'))
    arr, codes = z['arr'], z['codes']
    build_전량(s_일자)
    량 = np.load(os.path.join(folder_캐시(), f'초량_{s_일자}.npz'))['arr']
    a호 = np.load(os.path.join(folder_캐시(), f'호가_{s_일자}.npz'))['arr'] if build_호가(s_일자)[1] is not None else np.full((len(codes), arr.shape[1], 6), np.nan, np.float32)
    return np.concatenate([arr, 량[:, :, None], a호], axis=2), codes


# =====================================================================
# 종목 정보
# =====================================================================
_dic_종목 = None


def _종목표():
    """ 수집기가 받아 둔 전체종목 목록 → {종목코드: (종목명, 시장)} (최근 목록 우선) """
    global _dic_종목
    if _dic_종목 is None:
        _dic_종목 = {}
        folder = ut.폴더manager.FolderManager().dic_폴더정보['데이터|전체종목']
        for f in sorted(x for x in os.listdir(folder) if x.endswith('.pkl')):
            try:
                df = pd.read_pickle(os.path.join(folder, f))
                시장 = df['시장'] if '시장' in df.columns else pd.Series('기타', index=df.index)
                _dic_종목.update(dict(zip(df['종목코드'], zip(df['종목명'], 시장))))
            except Exception:
                pass
    return _dic_종목


def 종목명(s_코드):
    return _종목표().get(s_코드, ('', '기타'))[0]


def 시장구분(s_코드):
    return _종목표().get(s_코드, ('', '기타'))[1]


def 종목표시(s_코드):
    nm = 종목명(s_코드)
    return f'{nm}({s_코드})' if nm else s_코드


# =====================================================================
# 지표
# =====================================================================
def _rsum(x, n):
    c = np.concatenate([[0.0], np.cumsum(x, dtype=np.float64)])
    out = np.full(len(x), np.nan); out[n - 1:] = c[n:] - c[:-n]
    return out


def _lag(x, n):
    if n == 0:
        return x
    out = np.full(len(x), np.nan); out[n:] = x[:-n]
    return out


def 호가단위(x):
    """ 가격 → 호가 단위 (원, 배열 가능) """
    return np.select([x < 2000, x < 5000, x < 20000, x < 50000, x < 200000, x < 500000], [1, 5, 10, 50, 100, 500], 1000)


def _강도(b, s):
    return np.where(s > 0, np.minimum(b / np.where(s > 0, s, 1) * 100, 999), np.where(b > 0, 999, np.nan))


def 지표(a):
    """ 한 종목·하루 1초 배열 → 지표 (진입·청산에 쓰는 이평·창은 '거래 시간' 축) """
    p = a[:, 0].astype(np.float64); hi = a[:, 1].astype(np.float64); lo = a[:, 2].astype(np.float64)
    bv, sv = a[:, 3].astype(np.float64), a[:, 4].astype(np.float64)
    na_유효, na = a[:, 5].astype(np.float64), a[:, 11].astype(np.float64)
    d = dict(p=p, hi=hi, lo=lo, 매수량=bv, 매도량=sv, 체결건수=na_유효, 초=np.arange(len(p)))
    d['체결량전체'] = a[:, 12].astype(np.float64)
    d['대금1'] = d['체결량전체'] * p / 1e6                # 초당 거래대금 백만원 (체결량 × 1초 종가)
    d['일등락'] = (p / a[:, 7].astype(np.float64) - 1) * 100
    d['누적대금'] = a[:, 6].astype(np.float64)            # 백만원
    n분 = len(p) // 60; c분 = p[59:n분 * 60:60]                   # v12: 시계 분봉 종가 (분 m = 09:00+m, 1초 종가 ffill)
    M = np.arange(len(p)) // 60
    d['분수익3'] = np.where(M >= 4, (c분[np.clip(M - 1, 0, n분 - 1)] / c분[np.clip(M - 4, 0, n분 - 1)] - 1) * 100, np.nan)   # 진입 분 앞 완결 분봉 종가 ÷ 그 3분 전
    d['횟수배수기준'] = pd.Series(na_유효).rolling(270, min_periods=1).mean().shift(31).values   # v9: 직전 5분 전 ~ 31초 전(시계) 초당 체결횟수 평균 (단주 제외)
    d['고저폭60'] = (pd.Series(hi).rolling(60, min_periods=1).max().values / pd.Series(lo).rolling(60, min_periods=1).min().values - 1) * 100   # v6: 직전 60초(시계, 그 초 포함) 고저폭 %
    # 거래 정지 추정과 유효 초 (첫 체결 이후 · 정지 아님) - 정지 판정은 단주 포함 전체 체결
    정지 = np.zeros(len(p), bool)
    idx_체결 = np.flatnonzero(na > 0)
    if len(idx_체결):
        for j in np.flatnonzero(np.diff(idx_체결) - 1 >= N_정지최소초):
            a0, a1 = idx_체결[j] + 1, idx_체결[j + 1]
            if na[max(0, a0 - 30):a0].sum() >= N_정지직전건수:
                정지[a0:a1] = True
        유효 = (np.arange(len(p)) >= idx_체결[0]) & ~정지
    else:
        유효 = np.zeros(len(p), bool)
    d['정지'], d['유효'] = 정지, 유효
    d['정지후'] = np.nan_to_num(_lag(_rsum(정지.astype(float), max(N_정지후금지, 1)), 1)) > 0   # 정지가 풀린 지 N초 안
    # 호가 잔량비율 = 매수호가 총잔량 ÷ 매도호가 총잔량 + 5초 / 30초 이평 (시계 초, 그래프용)
    if np.isfinite(a[:, 13]).any():
        매도, 매수 = a[:, 13].astype(np.float64), a[:, 14].astype(np.float64)
        비 = pd.Series(np.where((매도 > 0) & (매수 > 0), 매수 / np.where(매도 > 0, 매도, 1), np.nan))
        d['잔량비'], d['잔량비5'], d['잔량비30'] = 비.values, 비.rolling(5, min_periods=5).mean().values, 비.rolling(30, min_periods=30).mean().values
    # 거래 시간 축 - 정지 구간과 첫 체결 전 초를 빼고 이어 붙여 계산한 뒤 원래 시각으로 되돌린다 (빠진 초는 비움)
    iv = np.flatnonzero(유효)
    def 복원(v_c):
        out = np.full(len(p), np.nan); out[iv] = v_c
        return out
    키 = ('속도5', '속도30', '체결량5', '체결량30', '대금5', '대금30', '체결강도5', '체결강도10', '변동초비율',
         '이평상승10', '이평하락10') + tuple(f'가격{n}' for n in sorted({n for ab in LI_이평 for n in ab})) \
        + tuple(f'{k}{a}_{b}' for a, b in LI_이평 for k in ('위', '교차', '경과', '돌파가'))
    if not len(iv):
        d.update({k_: np.full(len(p), np.nan) for k_ in 키})
        return d
    na_c, bv_c, sv_c, p_c = na_유효[iv], bv[iv], sv[iv], p[iv]
    d['속도5'], d['속도30'] = 복원(_rsum(na_c, 5) / 5), 복원(_rsum(na_c, 30) / 30)            # 체결횟수 5초 / 30초 이평
    량_c, 대_c = d['체결량전체'][iv], d['대금1'][iv]
    d['체결량5'], d['체결량30'] = 복원(_rsum(량_c, 5) / 5), 복원(_rsum(량_c, 30) / 30)
    d['대금5'], d['대금30'] = 복원(_rsum(대_c, 5) / 5), 복원(_rsum(대_c, 30) / 30)
    d['체결강도5'] = 복원(_강도(_rsum(bv_c, 5), _rsum(sv_c, 5)))
    d['체결강도10'] = 복원(_강도(_rsum(bv_c, 10), _rsum(sv_c, 10)))
    변동 = np.r_[0.0, (np.diff(p_c) != 0).astype(float)]                   # 직전 거래 초와 가격이 다른 초
    d['변동초비율'] = 복원(_lag(_rsum(변동, 240), 60) / 240 * 100)          # 5분 전 ~ 1분 전
    ma = {n: pd.Series(p_c).rolling(n).mean().to_numpy() for n in sorted({n for ab in LI_이평 for n in ab} | {5})}   # 가격 n초 이평
    for n, v in ma.items():
        d[f'가격{n}'] = 복원(v)
    n_ = np.arange(len(p_c))
    for a_, b_ in LI_이평:                                                  # 이평 짝마다 (키 끝 '{짧은}_{긴}')
        ok_ = ~np.isnan(ma[a_]) & ~np.isnan(ma[b_])
        아래, 위 = ok_ & (ma[a_] <= ma[b_]), ok_ & (ma[a_] > ma[b_])
        교차 = np.r_[False, 위[1:] & 아래[:-1]]                              # 직전 거래 초엔 이하, 이번 초에 위
        시작 = np.maximum.accumulate(np.where(교차, n_, -1))
        k_ = f'{a_}_{b_}'
        d[f'위{k_}'] = 복원(np.where(ok_, 위, np.nan))
        d[f'교차{k_}'] = 복원(교차.astype(float))
        d[f'경과{k_}'] = 복원(np.where(위 & (시작 >= 0), n_ - 시작, np.nan))   # v2: 위 구간에서 상향 돌파 초부터 지난 거래 초 (돌파 초 = 0, 돌파 없이 시작된 구간은 비움)
        d[f'돌파가{k_}'] = 복원(np.where(위 & (시작 >= 0), p_c[np.maximum(시작, 0)], np.nan))   # v4: 그 구간을 연 돌파 초의 1초 종가
    dm = np.r_[np.nan, np.diff(ma[5])]; 유10 = np.where(np.isnan(_lag(dm, 9)), np.nan, 1)
    d['이평상승10'], d['이평하락10'] = 복원(_rsum((dm > 0).astype(float), 10) * 유10), 복원(_rsum((dm < 0).astype(float), 10) * 유10)
    return d


# =====================================================================
# 진입·청산
# =====================================================================
def 쌍(c):
    """ 칸의 가격 이평 짝 → 지표 키 끝 ('5_30') """
    return '%d_%d' % c['이평']


def 횟수조건(d, c):
    if c['횟수'] == '문턱이평위':
        return (d['속도5'] >= N_체결횟수5) & (d['속도5'] > d['속도30'])
    if c['횟수'] == '이평위':
        return d['속도5'] > d['속도30']
    if c['횟수'] == '문턱':
        return d['속도5'] >= N_체결횟수5
    return np.ones(len(d['p']), bool)


def 창조건(d, c):
    """ ① 상향 돌파로 시작된 위 구간 (창이 있으면 돌파 후 창 초 이내) - 돌파 없이 시작된 구간은 거짓 """
    return d['경과' + 쌍(c)] <= (np.inf if c['창'] is None else c['창'])


def 호가조건(d, c):
    """ v4: 1초 종가 ≥ 돌파 초 종가 + N 호가 (호가 단위는 돌파 초 종가 기준) """
    if not c.get('호가'):
        return np.ones(len(d['p']), bool)
    b = d['돌파가' + 쌍(c)]
    return d['p'] >= b + c['호가'] * 호가단위(np.nan_to_num(b)) - 1e-9


def 제외조건(d, k):
    """ v9 ⑤ 제외 조건 k 에 걸리는 초 (값이 없으면 걸리지 않음) """
    if k == '횟수비':
        return np.nan_to_num(d['속도5'] / np.where(d['속도30'] > 0, d['속도30'], np.nan), nan=0) >= N_횟수비상한
    if k == '횟수배수':
        return np.nan_to_num(d['속도30'] / np.where(d['횟수배수기준'] > 0, d['횟수배수기준'], np.nan), nan=0) >= N_횟수배수상한
    return np.nan_to_num(d['변동초비율'], nan=100) < N_변동하한


def 제외(d, c):
    """ 칸의 제외 조건 중 하나라도 걸리면 거짓 """
    m = np.ones(len(d['p']), bool)
    for k in DIC_제외[c.get('제외', '없음')]:
        m &= ~제외조건(d, k)
    return m


def 충족(d, c):
    """ 초마다 ①(돌파 창·호가) · 공통 · ②③ 이 모두 켜졌나 """
    t = d['초']
    m = (t >= DIC_공통['시작']) & (t <= DIC_공통['종료']) & (d['p'] >= DIC_공통['가격min']) & ~d['정지후'] & 창조건(d, c) & 횟수조건(d, c) & 호가조건(d, c)
    if c['강도']:
        m &= d['체결강도5'] >= N_체결강도5
    if c.get('고저폭'):
        m &= d['고저폭60'] >= c['고저폭']
    if c.get('대금'):                                                       # v12 ⑥
        m &= d['누적대금'] / 100 < c['대금']
    if c.get('분수익') is not None:                                          # v12 ⑦
        m &= d['분수익3'] > c['분수익']
    return np.nan_to_num(m).astype(bool)


def 진입초(d, c):
    """ 상향 돌파로 시작된 위 구간마다 첫 충족 초 → 실제 초 배열 """
    iv = np.flatnonzero(d['유효'])
    if not len(iv):
        return np.array([], int)
    위, 교차 = d['위' + 쌍(c)][iv] == 1, d['교차' + 쌍(c)][iv] == 1
    구간 = np.where(위, np.cumsum(교차), 0)
    후보 = 충족(d, c)[iv] & (구간 > 0)
    k = np.flatnonzero(후보)
    _, first = np.unique(구간[k], return_index=True)
    ts = iv[k[first]]
    return ts[제외(d, c)[ts]]          # v9 ⑤: 살 초에 제외 조건이 걸리면 그 구간은 건너뛴다 (뒤로 미뤄 사지 않는다 - 미루면 끝물에 더 비싸게 산다)


def 거래생성(dic_지표, c):
    """ 진입 초마다 하향 돌파(진입에 쓴 짝의 짧은 이평 ≤ 긴 이평)인 첫 거래 초에 청산 - v8 손절이 있으면 그 전에 1초 저가가 손절선에 닿은 첫 초
        → (코드, 진입초, 청산초, 매수가, 청산가, 비용전%, 실측 순수익%, 사유) """
    li = []
    for code, d in dic_지표.items():
        ts = 진입초(d, c)
        if not len(ts):
            continue
        p = d['p']
        s_끝 = min(S_마감, len(p) - 1)
        아래 = np.flatnonzero(d['유효'] & (d['위' + 쌍(c)] == 0))
        for t in ts:
            j = np.searchsorted(아래, t + 1)
            s, why = (int(아래[j]), '하향돌파') if j < len(아래) and 아래[j] <= s_끝 else (s_끝, '마감')
            E, Xg = p[t] * (1 + N_실측매수 / 100), p[s]
            if c.get('손절'):                                                 # 같은 초면 손절이 먼저 (초 안에서 저가가 먼저 닿았다고 본다)
                선 = E * (1 - c['손절'] / 100)
                k = np.flatnonzero(d['lo'][t + 1:s + 1] <= 선 + 1e-9)
                if len(k):
                    s = t + 1 + int(k[0]); Xg, why = min(선, p[s]), '손절'
            w_, k_ = c.get('대기', (0, 0))
            if w_ and why == '하향돌파':
                s, Xg, why = 대기청산(d, c, E, s, s_끝)
            X = Xg * (1 - N_실측매도 / 100)
            li.append((code, int(t), s, E, X, (Xg / p[t] - 1) * 100, (X / E - 1) * 100 - N_실측비용, why))
    return li


def 대기청산(d, c, E, s, s_끝):
    """ v11: 하향 돌파 초 s 부터 - 종가가 매수가 −기준% 보다 위면 N초 기다린다 (다시 위로 올라오면 보유를 이어 가고 다음 하향 돌파에서 같은 규칙)
        → (청산초, 청산 종가 기준가, 사유) """
    w_, k_ = c['대기']
    p, lo, 유, 위 = d['p'], d['lo'], d['유효'], d['위' + 쌍(c)]
    선 = E * (1 - k_ / 100)
    while True:
        if p[s] <= 선 + 1e-9:                                      # 이미 기준보다 깊다 → 그 초에 판다
            return s, p[s], '하향돌파'
        끝 = min(s + w_, s_끝); 회복 = None
        for q in range(s + 1, 끝 + 1):
            if not 유[q]:
                continue
            if lo[q] == lo[q] and lo[q] <= 선 + 1e-9:               # 기다리는 중 기준선에 닿음
                return q, min(선, p[q]), '대기손실'
            if 위[q] == 1:
                회복 = q; break
        if 회복 is None:
            return 끝, p[끝], '대기만료' if 끝 < s_끝 else '마감'
        아래 = np.flatnonzero(유[회복 + 1:s_끝 + 1] & (위[회복 + 1:s_끝 + 1] == 0))   # 다시 위 → 다음 하향 돌파까지 보유
        if not len(아래):
            return s_끝, p[s_끝], '마감'
        s = 회복 + 1 + int(아래[0])


def _일자실행(args):
    s_일자, li_cfg = args
    warnings.simplefilter('ignore')
    arr, codes = 적재(s_일자)
    dic = {code: 지표(arr[i]) for i, code in enumerate(codes)}
    return [(c['id'], s_일자) + x for c in li_cfg for x in 거래생성(dic, c)]


def 실험(li_cfg, li_일자):
    with Pool(N_병렬) as pool:
        res = pool.map(_일자실행, [(s, li_cfg) for s in li_일자])
    return pd.DataFrame([r for x in res for r in x], columns=['id', '일자', '코드', '진입초', '청산초', '매수가', '청산가', '비용전', '수익', '사유'])


def 일부트(df, col, n=2000):
    """ 날짜를 다시 뽑는 부트스트랩 95% 구간 (거래당 평균) """
    g = df.groupby('일자')[col].agg(['sum', 'size'])
    if len(g) < 3:
        return np.nan, np.nan
    rng = np.random.default_rng(0); S, N = g['sum'].values, g['size'].values
    k = rng.integers(0, len(g), (n, len(g)))
    m = S[k].sum(1) / N[k].sum(1)
    return np.percentile(m, 2.5), np.percentile(m, 97.5)


def 요약(df, n_일):
    rows = []
    for c in LI_칸:
        x = df[df.id == c['id']]
        lo, hi = 일부트(x, '비용전') if len(x) else (np.nan, np.nan)
        일 = x.groupby('일자')['수익'].sum()
        rows.append(dict(id=c['id'], 건수=len(x), 하루=len(x) / n_일, 비용전=x.비용전.mean(), 비용전_하=lo, 비용전_상=hi, 수익=x.수익.mean(),
                         승률=(x.수익 > 0).mean() * 100 if len(x) else np.nan, 비용전승률=(x.비용전 > 0).mean() * 100 if len(x) else np.nan,
                         보유=(x.청산초 - x.진입초).median() if len(x) else np.nan, 이익일=(일 > 0).sum(), 일수=x.일자.nunique(),
                         애매=(x.비용전.abs() < N_애매).mean() * 100 if len(x) else np.nan, 애매평균=x[x.비용전.abs() < N_애매].비용전.mean(),
                         위1=(x.비용전 >= N_애매).mean() * 100 if len(x) else np.nan, 아래1=(x.비용전 <= -N_애매).mean() * 100 if len(x) else np.nan,
                         밖평균=x[x.비용전.abs() >= N_애매].비용전.mean(), 손절비율=(x.사유 == '손절').mean() * 100 if len(x) else np.nan))
    return pd.DataFrame(rows).set_index('id')


def 시도기록(li_일자, s_요약):
    """ 돌린 버전을 {work}/분석/백테스팅/이평돌파/시도기록.csv 에 한 줄씩 쌓는다 (같은 날짜를 몇 번 봤는지 세기 위해) """
    path = os.path.join(folder_이평(), '시도기록.csv')
    r = pd.DataFrame([dict(일시=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M'), 버전=S_버전, 칸=len(LI_칸), 일수=len(li_일자),
                           시작=min(li_일자), 끝=max(li_일자), 기준=s_요약)])
    r.to_csv(path, mode='a', header=not os.path.exists(path), index=False, encoding='utf-8-sig')


# =====================================================================
# 신호 후 평균 경로 · 그룹 분석
# =====================================================================
def _경로일자(args):
    s_일자, li = args
    z = np.load(os.path.join(folder_캐시(), f'초2_{s_일자}.npz'))
    arr, idx = z['arr'], {cd: k for k, cd in enumerate(z['codes'])}
    out = []
    for code, t in li:
        a, b = t - 60, t + 300
        if a >= 0 and b < arr.shape[1]:
            p = arr[idx[code], a:b + 1, 0].astype(float)
            out.append((p / p[60] - 1) * 100)
    return out


def 평균경로(df):
    """ 진입 초 −60 ~ +300초 가격 경로 (진입 초 종가 대비 %) """
    with Pool(N_병렬) as pool:
        res = pool.map(_경로일자, [(s, list(zip(g['코드'], g['진입초'].astype(int)))) for s, g in df.groupby('일자')])
    return np.array([r for y in res for r in y])


def _그룹일자(args):
    s_일자, li = args
    warnings.simplefilter('ignore')
    arr, codes = 적재(s_일자); idx = {cd: k for k, cd in enumerate(codes)}
    memo, out = {}, []
    for code, t in li:
        if code not in memo:
            memo[code] = 지표(arr[idx[code]])
        d, a = memo[code], arr[idx[code]]; p = d['p']
        dh = np.maximum.accumulate(np.where(np.isnan(d['hi']), -np.inf, d['hi']))[t - 1]
        m = (arr[:, t, 0] / arr[:, t, 7] - 1) * 100; m = m[np.isfinite(m)]      # 감시종목 전체의 전일 대비 등락 (진입 초)
        out.append(dict(가격=p[t], 일등락=d['일등락'][t], 고가거리=(p[t] / dh - 1) * 100, 누적대금=a[t, 6] / 100,
                        대금10=(d['매수량'][t - 9:t + 1].sum() + d['매도량'][t - 9:t + 1].sum()) * p[t] / 1e6,
                        상승300=(p[t] / p[t - 300] - 1) * 100 if t >= 300 else np.nan,
                        체결강도=d['체결강도5'][t], 속도5=d['속도5'][t], 변동초=d['변동초비율'][t],
                        정지이력='있음' if d['정지'][:t].any() else '없음',
                        시장등락=float(np.mean(m)) if len(m) else np.nan, 시장상승=float((m > 0).mean() * 100) if len(m) else np.nan))
    return out


def 그룹특징(df):
    """ 거래표 → 진입 순간 특징을 붙인 거래표 """
    df = df.sort_values(['일자', '코드', '진입초']).reset_index(drop=True)
    df['순번'] = (df.groupby(['일자', '코드']).cumcount() + 1).clip(upper=5).astype(str) + '번째'
    직전 = df.groupby(['일자', '코드'])['수익'].shift()
    df['직전'] = np.where(직전.isna(), '첫 거래', np.where(직전 > 0, '직전 수익', '직전 손실'))
    df['요일'] = pd.to_datetime(df['일자']).dt.dayofweek.map(dict(enumerate('월화수목금')))
    df['시장'] = df['코드'].map(시장구분)
    df['초'] = df['진입초']
    with Pool(N_병렬) as pool:
        res = pool.map(_그룹일자, [(s, list(zip(g['코드'], g['진입초'].astype(int)))) for s, g in df.groupby('일자', sort=True)])
    return pd.concat([df, pd.DataFrame([r for x in res for r in x])], axis=1)


_INF = float('inf')
# (분류, 뜻, 열, 방식, 경계, 이름) - 방식 cat = 값 그대로 / cut = 고정 경계 / q5 = IS 5등분 경계를 OOS 에 그대로
LI_그룹 = [
    ('시간대', '진입 시각', '초', 'cut', [0, 240, 600, 1800, 3600, 7200, 14400, 19800, _INF],
     ['09:01~', '09:04~', '09:10~', '09:30~', '10시~', '11시~', '13시~', '14:30~']),
    ('요일', '진입 요일', '요일', 'cat', None, ['월', '화', '수', '목', '금']),
    ('같은 종목 순번', '그 종목 당일 몇 번째 진입인가 (5번째 = 5번째 이후)', '순번', 'cat', None, [f'{k}번째' for k in range(1, 6)]),
    ('직전 거래', '같은 종목 당일 바로 앞 거래 결과', '직전', 'cat', None, ['첫 거래', '직전 수익', '직전 손실']),
    ('시장', '코스피 / 코스닥', '시장', 'cat', None, ['코스피', '코스닥']),
    ('거래 정지 이력', '당일 진입 전에 거래 정지(변동성완화장치 등)가 있었나', '정지이력', 'cat', None, ['없음', '있음']),
    ('가격대', '신호가 (원)', '가격', 'cut', [0, 5000, 10000, 20000, 50000, _INF], ['5천 미만', '5천~1만', '1만~2만', '2만~5만', '5만 이상']),
    ('전일 대비 등락', '진입 순간 전일 종가 대비 %', '일등락', 'cut', [-_INF, 0, 5, 10, 20, _INF], ['하락', '0~5%', '5~10%', '10~20%', '20% 이상']),
    ('당일 고가 대비', '진입가가 직전까지의 당일 고가보다 몇 % 아래인가', '고가거리', 'cut', [-_INF, -5, -2, -0.5, 0, _INF],
     ['-5% 아래', '-5~-2%', '-2~-0.5%', '-0.5~0%', '당일 신고가']),
    ('당일 누적 거래대금', '진입 순간까지 억원', '누적대금', 'q5', None, None),
    ('직전 10초 거래대금', '백만원', '대금10', 'q5', None, None),
    ('직전 5분 상승률', '%', '상승300', 'q5', None, None),
    ('체결강도', '진입 순간 5초 체결강도', '체결강도', 'q5', None, None),
    ('체결횟수', '진입 순간 5초 평균 (회)', '속도5', 'q5', None, None),
    ('평소 가격변동', '진입 5분 전~1분 전 가격이 변한 초 비율 %', '변동초', 'q5', None, None),
    ('감시종목 평균 등락', '진입 순간 감시종목 전체의 전일 대비 평균 %', '시장등락', 'q5', None, None),
    ('감시종목 상승 비율', '진입 순간 감시종목 중 전일보다 오른 종목 %', '시장상승', 'q5', None, None),
]
N_그룹최소 = 30          # IS·OOS 각각 이 건수 이상인 그룹만 판정
N_그룹차이 = 0.10        # 전체 평균과 %p 차이 - IS·OOS 모두 같은 방향으로 이만큼 벗어나야 '일관'


def 그룹분석(f_IS, f_OOS):
    """ → [(분류, 뜻, [(그룹, n_IS, 평균_IS, n_OOS, 평균_OOS, 승률_OOS)], 순위상관)] , 전체 평균 (IS, OOS) """
    res = []
    for 분류, 뜻, col, how, edges, names in LI_그룹:
        if how == 'cat':
            g_IS, g_OOS, 이름 = f_IS[col].astype(str), f_OOS[col].astype(str), names
        else:
            if how == 'q5':
                v = f_IS[col].dropna()
                if len(v) < 50:
                    continue
                q = np.unique(np.quantile(v, [.2, .4, .6, .8]))
                edges = [-_INF] + list(q) + [_INF]
                fm = (lambda x: f'{x:,.0f}') if abs(q).max() >= 100 else (lambda x: f'{x:.1f}')
                names = [f'~{fm(q[0])}'] + [f'{fm(a)}~{fm(b)}' for a, b in zip(q[:-1], q[1:])] + [f'{fm(q[-1])}~']
            cut = lambda s: pd.cut(s, edges, right=False, labels=names).astype(str)
            g_IS, g_OOS, 이름 = cut(f_IS[col]), cut(f_OOS[col]), names
        rows = []
        for nm in 이름:
            a, b = f_IS.loc[g_IS == nm, '수익'], f_OOS.loc[g_OOS == nm, '수익']
            rows.append((nm, len(a), a.mean() if len(a) else np.nan, len(b), b.mean() if len(b) else np.nan,
                         (b > 0).mean() * 100 if len(b) else np.nan))
        ok = [r for r in rows if r[1] >= N_그룹최소 and r[3] >= N_그룹최소]
        rho = pd.Series([r[2] for r in ok]).rank().corr(pd.Series([r[4] for r in ok]).rank()) if len(ok) >= 2 else np.nan
        res.append((분류, 뜻, rows, rho))
    return res, (f_IS['수익'].mean(), f_OOS['수익'].mean())


def 그룹판정(r, m):
    nm, n_i, a_i, n_o, a_o, _ = r
    if n_i < N_그룹최소 or n_o < N_그룹최소:
        return '표본 부족'
    d_i, d_o = a_i - m[0], a_o - m[1]
    if d_i >= N_그룹차이 and d_o >= N_그룹차이:
        return '일관 우세'
    if d_i <= -N_그룹차이 and d_o <= -N_그룹차이:
        return '일관 열세'
    return ''


# =====================================================================
# 그래프
# =====================================================================
RED, BLUE, GREEN, GRAY, FG, BG, PANEL, YEL, PUR = '#ff7b72', '#58a6ff', '#3fb950', '#8b949e', '#e6edf3', '#0d1117', '#161b22', '#d29922', '#d2a8ff'


def _plt():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for f in ('/System/Library/Fonts/Supplemental/AppleGothic.ttf',):
        if os.path.exists(f):
            font_manager.fontManager.addfont(f)
            plt.rcParams['font.family'] = 'AppleGothic'
    plt.rcParams.update({'axes.unicode_minus': False, 'figure.facecolor': BG, 'axes.facecolor': PANEL,
                         'axes.edgecolor': '#30363d', 'axes.labelcolor': FG, 'xtick.color': FG, 'ytick.color': FG,
                         'text.color': FG, 'legend.facecolor': PANEL, 'legend.edgecolor': '#30363d', 'grid.color': '#30363d'})
    return plt


def _img(fig, dpi=90):
    plt = _plt()
    b = io.BytesIO(); fig.savefig(b, format='png', dpi=dpi, bbox_inches='tight'); plt.close(fig)
    return f'<img src="data:image/png;base64,{base64.b64encode(b.getvalue()).decode()}">'


def 경로그림(경로):
    plt = _plt()
    fig, ax = plt.subplots(figsize=(10, 3.8))
    xs = np.arange(-60, 301)
    for k, col in (('IS', FG), ('OOS', YEL)):
        X = 경로[k]
        if len(X):
            ax.plot(xs, np.nanmean(X, axis=0), color=col, lw=1.6, label=f'{k} 평균 ({len(X):,}건)')
            ax.fill_between(xs, np.nanpercentile(X, 25, axis=0), np.nanpercentile(X, 75, axis=0), color=col, alpha=.10)
    ax.axvline(0, color=RED, lw=1); ax.axhline(0, color=GREEN, ls='--', lw=1)
    n_비용 = N_실측비용 + N_실측매수 + N_실측매도
    ax.axhline(n_비용, color=GRAY, ls=':', lw=1); ax.text(300, n_비용, f' 실측 비용 {n_비용:.2f}%', color=GRAY, va='bottom', ha='right', fontsize=8)
    ax.axhline(N_문턱비용전, color=GREEN, ls=':', lw=1); ax.text(300, N_문턱비용전, f' 통과 문턱 {N_문턱비용전}%', color=GREEN, va='bottom', ha='right', fontsize=8)
    ax.set_xlabel('신호 기준 초'); ax.set_ylabel('신호 초 종가 대비 %'); ax.legend(fontsize=8, loc='upper left'); ax.grid(alpha=.3)
    return _img(fig)


def 분포그림(r_IS, r_OOS, 폭=0.25, lo=-4.0, hi=6.0):
    """ 수익률 분포 - 가로 수익률(%) · 세로 매매 건수, IS·OOS 나란히 """
    plt = _plt()
    edges = np.arange(lo, hi + 폭 / 2, 폭)
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.6), sharex=True, sharey=True)
    for ax, (nm, r) in zip(axs, (('IS', r_IS), ('OOS', r_OOS))):
        v = np.clip(np.asarray(r, float), lo + 1e-9, hi - 1e-9)    # 범위 밖은 양 끝 칸에 합친다
        n, _ = np.histogram(v, edges)
        mid = (edges[:-1] + edges[1:]) / 2
        ax.bar(mid, n, width=폭 * .92, color=[RED if m > 0 else BLUE for m in mid], alpha=.85)
        ax.axvline(0, color=GREEN, lw=1.1, label='손익 0')
        if len(r):
            ax.axvline(float(np.mean(r)), color=FG, lw=1, ls='--', label=f'평균 {np.mean(r):+.2f}%')
        ax.set_title(f"{nm}  {len(r):,}건 · 승률 {(np.asarray(r) > 0).mean() * 100 if len(r) else 0:.0f}% · 중앙값 {np.median(r) if len(r) else 0:+.2f}%", fontsize=10)
        ax.set_xlabel('수익률 (%)'); ax.grid(alpha=.3, axis='y')
        ax.legend(fontsize=8, loc='upper right', ncol=2)
    axs[0].set_ylabel('매매 건수')
    fig.tight_layout()
    return _img(fig)


def 보유그림(x_IS, x_OOS):
    """ 보유 시간별 거래당 비용 전 수익과 거래 비중 """
    plt = _plt()
    edges = [0, 3, 5, 10, 20, 30, 60, 120, 300, 1e9]; names = ['~2초', '3~4', '5~9', '10~19', '20~29', '30~59', '60~119', '120~299', '300초~']
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.4))
    xs = np.arange(len(names))
    for j, (nm, x) in enumerate((('IS', x_IS), ('OOS', x_OOS))):
        g = x.groupby(pd.cut(x.청산초 - x.진입초, edges, right=False, labels=names), observed=False)
        v, n = np.nan_to_num(g['비용전'].mean().reindex(names).values), g.size().reindex(names).values
        ax[0].bar(xs + (j - .5) * .38, v, width=.36, color=[RED if t > 0 else BLUE for t in v], alpha=.45 if j == 0 else .95, label=nm)
        ax[1].bar(xs + (j - .5) * .38, n / max(n.sum(), 1) * 100, width=.36, color=GRAY, alpha=.45 if j == 0 else .95, label=nm)
    ax[0].axhline(0, color=GREEN, lw=1); ax[0].set_title('보유 시간별 거래당 비용 전 수익 %', fontsize=10)
    ax[1].set_title('보유 시간별 거래 비중 %', fontsize=10)
    for A in ax:
        A.set_xticks(xs); A.set_xticklabels(names, fontsize=7.5); A.grid(alpha=.3, axis='y'); A.legend(fontsize=8)
    fig.tight_layout()
    return _img(fig)


def 그룹그림(res, m):
    """ 분류마다 그룹별 거래당 수익률 %, IS 흐린 막대 · OOS 진한 막대 """
    plt = _plt()
    n = len(res); nc = 3; nr = (n + nc - 1) // nc
    fig, axs = plt.subplots(nr, nc, figsize=(15, 3.1 * nr))
    axs = np.atleast_1d(axs).ravel()
    for ax, (분류, 뜻, rows, rho) in zip(axs, res):
        x = np.arange(len(rows)); w = .38
        v_i = [r[2] if r[1] else np.nan for r in rows]; v_o = [r[4] if r[3] else np.nan for r in rows]
        vv = np.array([v for v in v_i + v_o if v == v] + [0.0])
        lo, hi = min(-.4, vv.min() * 1.15), max(.3, vv.max() * 1.15)
        for dd, off, al, nm in ((v_i, -w / 2, .35, 'IS'), (v_o, w / 2, .95, 'OOS')):
            ax.bar(x + off, np.nan_to_num(dd), width=w, color=[RED if v > 0 else BLUE for v in np.nan_to_num(dd)], alpha=al,
                   edgecolor=FG if nm == 'IS' else 'none', lw=.4, label=f'{nm} 거래당 수익률 %')
        for j, r in enumerate(rows):
            if 그룹판정(r, m).startswith('일관'):
                ax.text(j, hi * .8, '★', color=GREEN, ha='center', va='center', fontsize=12)
        ax.axhline(0, color=GREEN, lw=1)
        ax.axhline((m[0] + m[1]) / 2, color=FG, lw=.8, ls=':')
        ax.set_xticks(x); ax.set_xticklabels([f'{r[0]}\n{r[1]}/{r[3]}' for r in rows], fontsize=7)
        ax.set_title(f'{분류}  (IS·OOS 순위상관 {rho:+.2f})' if rho == rho else 분류, fontsize=10)
        ax.set_ylim(lo, hi); ax.grid(alpha=.3, axis='y'); ax.tick_params(axis='y', labelsize=7)
    for ax in axs[n:]:
        ax.axis('off')
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, loc='upper center', ncol=2, fontsize=9, bbox_to_anchor=(.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, .975))
    return _img(fig, dpi=80)


def 종목지속(f_IS, f_OOS, n최소=3):
    """ 종목별: IS 에서 좋던 종목이 OOS 에서도 좋은가 → (그림, 순위상관, 3등분 표, 종목 수) """
    plt = _plt()
    a = f_IS.groupby('코드')['수익'].agg(['size', 'mean']); b = f_OOS.groupby('코드')['수익'].agg(['size', 'mean'])
    j = a.join(b, lsuffix='_IS', rsuffix='_OOS', how='inner')
    j = j[(j.size_IS >= n최소) & (j.size_OOS >= n최소)]
    if len(j) < 9:
        return '', np.nan, [], len(j)
    rho = j['mean_IS'].rank().corr(j['mean_OOS'].rank())
    j['3등분'] = pd.qcut(j['mean_IS'].rank(method='first'), 3, labels=['IS 하위 ⅓', 'IS 중간 ⅓', 'IS 상위 ⅓'])
    rows = []
    for k, g in j.groupby('3등분', observed=True):
        x = f_OOS[f_OOS['코드'].isin(g.index)]['수익']
        rows.append((k, len(g), f_IS[f_IS['코드'].isin(g.index)]['수익'].mean(), len(x), x.mean()))
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    ax.scatter(j['mean_IS'], j['mean_OOS'], s=np.clip(j.size_IS + j.size_OOS, 6, 80) * 2, color=YEL, alpha=.55, edgecolors='none', label='종목 (크기 = 거래 수)')
    ax.axhline(0, color=GREEN, ls='--', lw=1); ax.axvline(0, color=GREEN, ls='--', lw=1)
    ax.set_xlabel('IS 거래당 %'); ax.set_ylabel('OOS 거래당 %'); ax.grid(alpha=.3); ax.legend(fontsize=8, loc='upper left')
    ax.set_title(f'IS·OOS 모두 {n최소}건 이상인 종목 {len(j)}개 · 순위상관 {rho:+.2f}', fontsize=10)
    return _img(fig), rho, rows, len(j)


def 거래그래프(d, r, c, s_제목):
    """ 거래 그래프 (진입 −120초 ~ 청산 +120초) - 가격 · ② 체결횟수 · 체결량 · 거래대금 · ③ 체결강도 · 호가 · 가격 추세 · 평소 가격변동 · 조건 충족 """
    from matplotlib.ticker import FuncFormatter, FixedLocator, NullLocator
    plt = _plt()
    t, s = int(r['진입초']), int(r['청산초'])
    a, b = max(0, t - 120), min(len(d['p']) - 1, s + 120)
    x = np.arange(a, b + 1) - t
    fig, ax = plt.subplots(9, 1, figsize=(9, 13.2), sharex=True, gridspec_kw=dict(height_ratios=[2.2, 1, 1, 1, 1, 1, 1, 1, 1.1]))
    leg = dict(fontsize=6.5, loc='upper left', ncol=3, framealpha=.55, handlelength=1.2, columnspacing=.8, borderpad=.3)
    # ① 가격 - 1초 종가 · 5초 / 30초 이평 · 상향 돌파 초
    ax[0].plot(x, d['p'][a:b + 1], color=FG, lw=1.2, label='가격(1초 종가)')
    n1, n2 = c['이평']; k2 = 쌍(c)
    ax[0].plot(x, d[f'가격{n1}'][a:b + 1], color=YEL, lw=1.0, label=f'가격 {n1}초 이평')
    ax[0].plot(x, d[f'가격{n2}'][a:b + 1], color=PUR, lw=1.0, label=f'가격 {n2}초 이평')
    k_ = np.flatnonzero(np.nan_to_num(d['교차' + k2][a:b + 1]) == 1)
    if len(k_):
        ax[0].scatter(x[k_], d[f'가격{n1}'][a:b + 1][k_], color=YEL, marker='o', s=14, zorder=4, label='상향 돌파')
    if c.get('호가'):
        b_ = d['돌파가' + k2][a:b + 1]
        ax[0].plot(x, b_ + c['호가'] * 호가단위(np.nan_to_num(b_)), color=GREEN, lw=.9, ls=':', label=f"돌파가 +{c['호가']}호가")
    if c.get('손절'):
        ax[0].axhline(r['매수가'] * (1 - c['손절'] / 100), color=BLUE, lw=.9, ls='--', label=f"손절선 -{c['손절']:g}%")
    ax[0].axvspan(0, s - t, color=RED if r['수익'] > 0 else BLUE, alpha=.12)
    ax[0].scatter([0], [r['매수가']], color=RED, marker='^', s=60, zorder=5, label='매수')
    ax[0].scatter([s - t], [r['청산가']], color=BLUE, marker='v', s=60, zorder=5, label=f"청산({r['사유']})")
    ax[0].set_ylabel('① 가격'); ax[0].grid(alpha=.3)
    ax[0].legend(fontsize=7, loc='upper left', ncol=4, framealpha=.55, borderaxespad=.15, borderpad=.3, handlelength=1.2, columnspacing=.8)
    ax[0].set_title(s_제목, color=FG, fontsize=10)
    # ② 체결횟수 - 5초 / 30초 이평 + 문턱
    ax[1].plot(x, d['속도5'][a:b + 1], color=YEL, lw=1.2, label='5초 이평')
    ax[1].plot(x, d['속도30'][a:b + 1], color=PUR, lw=1.2, label='30초 이평')
    if c['횟수'] in ('문턱', '문턱이평위'):
        ax[1].axhline(N_체결횟수5, color=GREEN, ls='--', lw=1, label=f'5초 문턱 {N_체결횟수5}')
    ax[1].set_ylim(bottom=0); ax[1].legend(**leg)
    ax[1].set_ylabel('② 체결횟수\n(단주 제외)', fontsize=8)
    # 체결량 - 초당 체결량 막대(1·2주 단주 포함) + 5초 / 30초 이평
    vol, 량5, 량30 = d['체결량전체'], d['체결량5'], d['체결량30']
    ax[2].bar(x, vol[a:b + 1], width=1, color=GRAY, alpha=.55, lw=0, label='초당 체결량')
    ax[2].plot(x, 량5[a:b + 1], color=YEL, lw=1.2, label='5초 이평')
    ax[2].plot(x, 량30[a:b + 1], color=PUR, lw=1.2, label='30초 이평')
    v_ = vol[a:b + 1]; 이평_ = np.nan_to_num(량5[a:b + 1])
    ax[2].set_ylim(0, max(np.nanpercentile(v_, 99) if len(v_) else 1, 이평_.max() if len(이평_) else 1, 1) * 1.15)   # 한 초짜리 큰 체결에 눌리지 않게 99% 선에서 자른다
    ax[2].yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v / 1e4:g}만' if v >= 1e4 else f'{v:g}'))
    ax[2].legend(**leg); ax[2].set_ylabel('체결량(주)\n(단주 포함)', fontsize=8); ax[2].tick_params(axis='y', labelsize=7)
    # 거래대금 - 초당 거래대금 막대(체결량 × 1초 종가, 백만원) + 5초 / 30초 이평
    대, 대5, 대30 = d['대금1'], d['대금5'], d['대금30']
    ax[3].bar(x, 대[a:b + 1], width=1, color=GRAY, alpha=.55, lw=0, label='초당 거래대금')
    ax[3].plot(x, 대5[a:b + 1], color=YEL, lw=1.2, label='5초 이평')
    ax[3].plot(x, 대30[a:b + 1], color=PUR, lw=1.2, label='30초 이평')
    v_ = 대[a:b + 1]; 이평_ = np.nan_to_num(대5[a:b + 1])
    ax[3].set_ylim(0, max(np.nanpercentile(v_, 99) if len(v_) else 1, 이평_.max() if len(이평_) else 1, .1) * 1.15)
    ax[3].yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v / 100:g}억' if v >= 100 else f'{v:g}백만' if v else '0'))
    ax[3].legend(**leg); ax[3].set_ylabel('거래대금\n(초당)', fontsize=8); ax[3].tick_params(axis='y', labelsize=7)
    # ③ 체결강도 - 5초(조건) · 10초(참고)
    ax[4].plot(x, np.clip(d['체결강도5'][a:b + 1], 10, 999), color=RED, lw=1.2, label='5초 체결강도')
    ax[4].plot(x, np.clip(d['체결강도10'][a:b + 1], 10, 999), color=GRAY, lw=.8, alpha=.8, label='10초 (참고)')
    if c['강도']:
        ax[4].axhline(N_체결강도5, color=GREEN, ls='--', lw=1, label=f'문턱 {N_체결강도5}')
    ax[4].axhline(100, color=GRAY, lw=.6)
    ax[4].set_yscale('log'); ax[4].set_yticks([10, 100, 1000]); ax[4].set_yticklabels(['10', '100', '1000'])
    ax[4].legend(**dict(leg, loc='lower left')); ax[4].set_ylim(8, 1300); ax[4].set_ylabel('③ 체결강도\n(100=균형)', fontsize=8)
    # 호가 잔량비율 - 매수호가 총잔량 ÷ 매도호가 총잔량 (호가 수집은 10/12 부터)
    if '잔량비' in d and np.isfinite(d['잔량비'][a:b + 1]).any():
        비_ = d['잔량비'][a:b + 1]
        ax[5].plot(x, 비_, color=GRAY, lw=.8, alpha=.8, label='잔량비율 (매수 ÷ 매도 총잔량)')
        ax[5].plot(x, d['잔량비5'][a:b + 1], color=YEL, lw=1.2, label='5초 이평')
        ax[5].plot(x, d['잔량비30'][a:b + 1], color=PUR, lw=1.2, label='30초 이평')
        ax[5].axhline(1, color=GRAY, lw=.6)
        ax[5].set_yscale('log'); ax[5].set_ylim(min(np.nanpercentile(비_, 1), .8) / 1.2, max(np.nanpercentile(비_, 99), 1.25) * 1.2)   # 1 을 가운데 두고 위아래가 같은 비율로
        ax[5].yaxis.set_major_locator(FixedLocator([v for v in (.1, .2, .5, 1, 2, 5, 10, 20) if ax[5].get_ylim()[0] <= v <= ax[5].get_ylim()[1]]))
        ax[5].yaxis.set_minor_locator(NullLocator()); ax[5].yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:g}'))
        ax[5].legend(**leg)
    else:
        ax[5].text(.5, .5, '호가 자료 없음 (호가 수집은 10/12 부터)', transform=ax[5].transAxes, ha='center', va='center', color=GRAY, fontsize=8)
        ax[5].set_yticks([])
    ax[5].set_ylabel('호가\n잔량비율', fontsize=8); ax[5].tick_params(axis='y', labelsize=7)
    # 가격 추세 (참고) - 가격 5초 이평이 직전 10초 중 몇 번 올랐고 몇 번 내렸나
    ax[6].step(x, d['이평상승10'][a:b + 1], where='mid', color=RED, lw=1.1, label='직전 10초 중 오른 횟수')
    ax[6].step(x, d['이평하락10'][a:b + 1], where='mid', color=BLUE, lw=1.1, label='내린 횟수')
    ax[6].set_ylim(-.8, 16); ax[6].set_yticks([0, 5, 10]); ax[6].legend(**leg)
    ax[6].set_ylabel('가격 추세\n(5초 이평)', fontsize=8)
    # 평소 가격 변동 (참고) - 5분 전 ~ 1분 전 가격이 바뀐 초 비율
    ax[7].plot(x, d['변동초비율'][a:b + 1], color=YEL, lw=1.1, label='5분 전~1분 전 가격이 바뀐 초 비율%')
    ax[7].set_ylim(0, 105); ax[7].legend(**dict(leg, loc='lower left'))
    ax[7].set_ylabel('평소\n가격변동%', fontsize=8)
    # 조건 충족 띠 - 상향 돌파로 시작된 위 구간에서 '전부 충족'이 처음 켜지는 초가 진입 (1초만 켜져도 1초 폭으로)
    li_띠 = [(f'① 가격 {n1}초 이평 > {n2}초 이평', d['위' + k2] == 1), ('① 상향 돌파 초', d['교차' + k2] == 1)] \
        + ([(f'① 상향 돌파 후 {c["창"]}초 이내', 창조건(d, c))] if c['창'] else []) \
        + ([(f"① 돌파 초 종가 +{c['호가']}호가 이상", 호가조건(d, c))] if c.get('호가') else []) \
        + ([(f'② 체결횟수 5초 이평 ≥ {N_체결횟수5}', d['속도5'] >= N_체결횟수5)] if c['횟수'] in ('문턱', '문턱이평위') else []) \
        + ([('② 체결횟수 5초 이평 > 30초 이평', d['속도5'] > d['속도30'])] if c['횟수'] in ('이평위', '문턱이평위') else []) \
        + ([(f'③ 5초 체결강도 ≥ {N_체결강도5}', d['체결강도5'] >= N_체결강도5)] if c['강도'] else []) \
        + ([(f"④ 직전 60초 고저폭 ≥ {c['고저폭']}%", d['고저폭60'] >= c['고저폭'])] if c.get('고저폭') else []) \
        + [(f'⑤ 아님: {DIC_제외이름[k]}', ~제외조건(d, k)) for k in DIC_제외[c.get('제외', '없음')]] \
        + ([(f"⑥ 당일 누적 대금 < {c['대금']}억", d['누적대금'] / 100 < c['대금'])] if c.get('대금') else []) \
        + ([(f"⑦ 분봉 3분 수익 > {c['분수익']:g}%", d['분수익3'] > c['분수익'])] if c.get('분수익') is not None else []) \
        + [(f'정지 풀린 뒤 {N_정지후금지}초 지남', ~d['정지후']), ('①~④ 충족 (구간 첫 초에 ⑤ 안 걸리면 진입)' if DIC_제외[c.get('제외', '없음')] else '전부 충족 (구간 첫 초 = 진입)', 충족(d, c))]
    for j, (nm, m) in enumerate(li_띠):
        mm = np.nan_to_num(np.asarray(m, dtype=float)[a:b + 1]).astype(bool)
        y0 = len(li_띠) - 1 - j
        e_ = np.diff(np.r_[0, mm.astype(int), 0]); i0s, i1s = np.flatnonzero(e_ == 1), np.flatnonzero(e_ == -1)
        col = GREEN if j == len(li_띠) - 1 else YEL
        ax[8].broken_barh([(x[i0] - .5, i1 - i0) for i0, i1 in zip(i0s, i1s)], (y0 + .1, .8), facecolors=col, edgecolors=col, lw=.8,
                          alpha=.9 if j == len(li_띠) - 1 else .6)
    ax[8].set_yticks([len(li_띠) - 1 - j + .5 for j in range(len(li_띠))]); ax[8].set_yticklabels([n for n, _ in li_띠], fontsize=6.5)
    ax[8].set_ylim(0, len(li_띠)); ax[8].set_ylabel('조건 충족', fontsize=8); ax[8].set_xlabel('진입 기준 초')
    # 거래 정지 구간 - 회색 띠 (지표는 이 구간을 건너뛰어 계산했다)
    st = d['정지'][a:b + 1]
    if st.any():
        e_ = np.diff(np.r_[0, st.astype(int), 0]); i0s, i1s = np.flatnonzero(e_ == 1), np.flatnonzero(e_ == -1)
        for k, A in enumerate(ax):
            for q, (i0, i1) in enumerate(zip(i0s, i1s)):
                A.axvspan(x[i0], x[i1 - 1] + 1, color=GRAY, alpha=.18, lw=0, label='거래 정지' if (k == 0 and q == 0) else None)
        ax[0].legend(fontsize=7, loc='upper left', ncol=4, framealpha=.55, borderaxespad=.15, borderpad=.3, handlelength=1.2, columnspacing=.8)
    for A in ax:
        A.axvline(0, color=RED, lw=.8); A.axvline(s - t, color=BLUE, lw=.8)
    fig.subplots_adjust(hspace=.08)
    return _img(fig, dpi=80)


# =====================================================================
# 실행
# =====================================================================
def run(b_텔레그램=True):
    warnings.simplefilter('ignore')
    캐시보충(min(3, N_병렬))
    li_일자 = li_캐시일자()
    li_IS, li_OOS = 분할(li_일자)
    folder = folder_이평(); os.makedirs(folder, exist_ok=True)
    print(f'이평돌파 {S_버전} · {len(li_일자)}일 ({li_일자[0]}~{li_일자[-1]}) · IS {len(li_IS)} · OOS {len(li_OOS)}', flush=True)

    df_IS, df_OOS = 실험(LI_칸, li_IS), 실험(LI_칸, li_OOS)
    df_IS.to_pickle(os.path.join(folder, f'{S_버전}_거래_IS.pkl')); df_OOS.to_pickle(os.path.join(folder, f'{S_버전}_거래_OOS.pkl'))
    s_IS, s_OOS = 요약(df_IS, len(li_IS)), 요약(df_OOS, len(li_OOS))
    print(s_IS.round(3).to_string(), '\n', s_OOS.round(3).to_string(), flush=True)

    x_IS, x_OOS = df_IS[df_IS.id == S_기준].copy(), df_OOS[df_OOS.id == S_기준].copy()
    경로 = {'IS': 평균경로(x_IS), 'OOS': 평균경로(x_OOS)}
    그룹 = (그룹특징(x_IS), 그룹특징(x_OOS))
    그룹[0].to_pickle(os.path.join(folder, f'{S_버전}_그룹_IS.pkl')); 그룹[1].to_pickle(os.path.join(folder, f'{S_버전}_그룹_OOS.pkl'))
    i, o = s_IS.loc[S_기준], s_OOS.loc[S_기준]
    시도기록(li_일자, f'IS 비용전 {i.비용전:+.3f} 실측 {i.수익:+.3f} / OOS 비용전 {o.비용전:+.3f} 실측 {o.수익:+.3f}')
    html = 리포트(li_IS, li_OOS, s_IS, s_OOS, x_IS, x_OOS, 경로, 그룹, (손절짝(df_IS), 손절짝(df_OOS)), (대기짝(df_IS), 대기짝(df_OOS)), (df_IS, df_OOS))

    dic_config = ut.도구manager.ToolManager().config로딩()
    with open(os.path.join(dic_config['folder_설정'], 'server_info.json'), mode='rt', encoding='utf-8') as f:
        dic_서버 = json.load(f)
    folder_웹 = os.path.join(dic_서버['folder']['server_kakao'], S_리포트폴더)
    s_파일 = f'{pd.Timestamp.now():%Y%m%d}_이평돌파_{S_버전}.html'
    os.makedirs(folder_웹, exist_ok=True)
    with open(os.path.join(folder_웹, s_파일), 'w', encoding='utf-8') as f:
        f.write(html)
    s_url = f'http://{dic_서버["sftp"]["hostname"]}/{os.path.basename(dic_서버["folder"]["server_kakao"])}/{S_리포트폴더}/{urllib.parse.quote(s_파일)}'
    print(s_파일, flush=True)

    if b_텔레그램:
        import requests
        from xapi.API_telegram import TelegramAPI
        if requests.head(s_url, timeout=10).status_code == 200:
            s_msg = (f'[이평돌파 {S_버전}] 리포트 완료\n'
                     + '\n'.join(f"· {c['이름']}: 비용 전 IS {s_IS.loc[c['id']].비용전:+.2f}% / OOS {s_OOS.loc[c['id']].비용전:+.2f}% · 애매 {s_OOS.loc[c['id']].애매:.0f}%"
                                 for c in LI_칸 if c.get('호가') == max(LI_호가) and c.get('대기', (0, 0))[1] in (0, 1))
                     + f'\n· 통과 문턱: 비용 전 +{N_문턱비용전}% · 실측 +{N_문턱실측}% (IS·OOS 양쪽)')
            TelegramAPI().send_메세지(s_메세지=s_msg, li_링크=[(s_파일, s_url)])
    return s_IS, s_OOS


def 손절짝(df):
    """ v8: 같은 진입(호가·고저폭이 같은 칸)에서 손절 칸과 손절 없음 칸을 짝지어 - 손절로 끊은 거래가 손절이 없었으면 어떻게 끝났나 """
    rows = []
    for c in LI_칸:
        if not c.get('손절'):
            continue
        b_id = c['id'].replace(f"|손절{c['손절']:g}|", '|손절0|')
        a, b = df[df.id == c['id']], df[df.id == b_id]
        j = a.merge(b, on=['일자', '코드', '진입초'], suffixes=('', '_없음'))
        k = j[j.사유 == '손절']
        rows.append(dict(id=c['id'], 호가=c['호가'], 손절=c['손절'], 건수=len(j), 손절건수=len(k), 손절비율=len(k) / max(len(j), 1) * 100,
                         손절평균=k.비용전.mean(), 없었으면=k.비용전_없음.mean(), 회복=(k.비용전_없음 > 0).mean() * 100 if len(k) else np.nan,
                         더깊음=(k.비용전_없음 < k.비용전).mean() * 100 if len(k) else np.nan, 변화=(j.비용전 - j.비용전_없음).mean()))
    return pd.DataFrame(rows)


def 대기짝(df):
    """ v11: 같은 진입에서 대기 칸과 대기 없음 칸을 짝지어 - 대기 때문에 청산이 바뀐 거래가 어떻게 됐나 """
    rows = []
    for c in LI_칸:
        w_, k_ = c.get('대기', (0, 0))
        if not w_:
            continue
        b_id = c['id'].replace(f'|대기{w_}_{k_:g}|', '|대기0_0|')
        j = df[df.id == c['id']].merge(df[df.id == b_id], on=['일자', '코드', '진입초'], suffixes=('', '_없음'))
        k = j[j.청산초 != j.청산초_없음]
        rows.append(dict(id=c['id'], 대기=w_, 기준=k_, 건수=len(j), 바뀜=len(k) / max(len(j), 1) * 100, 바뀐평균=k.비용전.mean(), 없었으면=k.비용전_없음.mean(),
                         좋아짐=(k.비용전 > k.비용전_없음).mean() * 100 if len(k) else np.nan, 대기손실=(j.사유 == '대기손실').mean() * 100,
                         보유=(j.청산초 - j.진입초).median(), 변화=(j.비용전 - j.비용전_없음).mean()))
    return pd.DataFrame(rows)


def 시간대(df):
    """ v12: 칸 × 시간대 → (건수, 비용 전 거래당) """
    rows = {}
    for c in LI_칸:
        x = df[df.id == c['id']]
        rows[c['id']] = [(len(y), y.비용전.mean()) for y in (x[(x.진입초 >= a) & (x.진입초 < b)] for a, b, _ in LI_시간대)]
    return rows


def 리포트(li_IS, li_OOS, s_IS, s_OOS, x_IS, x_OOS, 경로, 그룹, 손절표=None, 대기표=None, 원장=None):
    def pc(v, dgt=2):
        if v != v: return '-'
        return f'<span class="{"pos" if v > 0 else "neg" if v < 0 else ""}">{v:+.{dgt}f}%</span>'

    def table(head, rows, left=False):
        h = ''.join(f'<th>{x}</th>' for x in head)
        b = ''.join('<tr>' + ''.join(f'<td>{x}</td>' for x in r) + '</tr>' for r in rows)
        return f'<div class="tw"><table class="{"left" if left else ""}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'

    def 통과(s_):
        return f'<span style="color:{GREEN}">통과</span>' if s_.비용전 >= N_문턱비용전 and s_.수익 >= N_문턱실측 else '미달'

    c = next(c for c in LI_칸 if c['id'] == S_기준)
    i, o = s_IS.loc[S_기준], s_OOS.loc[S_기준]
    n_비용 = N_실측비용 + N_실측매수 + N_실측매도
    li_전체 = li_IS + li_OOS

    # 칸 비교
    li_칸 = []
    for c_ in LI_칸:
        for nm, s_ in (('IS', s_IS.loc[c_['id']]), ('OOS', s_OOS.loc[c_['id']])):
            li_칸.append([c_['이름'] if nm == 'IS' else '', nm, f'{s_.건수:,.0f}', f'{s_.하루:,.1f}', pc(s_.비용전, 3), f'{s_.비용전_하:+.2f} ~ {s_.비용전_상:+.2f}',
                         pc(s_.수익, 3), f'{s_.승률:.0f}%', f'{s_.비용전승률:.0f}%', f'{s_.보유:.0f}초', f'{s_.이익일:.0f}/{s_.일수:.0f}', 통과(s_)])

    # 기준 규칙 성적
    li_구분 = [[nm, f'{len(x):,}', pc(x.비용전.mean(), 3), pc(x.수익.mean(), 3), pc(x.수익.median()), f'{(x.수익 > 0).mean() * 100:.0f}%',
               f'{(x.청산초 - x.진입초).median():.0f}초', f'{x.일자.nunique()}', ' · '.join(f'{k} {v:,}' for k, v in x.사유.value_counts().items())]
              for nm, x in (('IS', x_IS), ('OOS', x_OOS))]

    # 그룹 분석 (기준 규칙)
    f_IS, f_OOS = 그룹
    res_그룹, m_그룹 = 그룹분석(f_IS, f_OOS)
    li_그룹요약 = [[분류, 뜻, f'{rho:+.2f}' if rho == rho else '-',
                 ' · '.join(r[0] for r in rows if 그룹판정(r, m_그룹) == '일관 우세') or '-',
                 ' · '.join(r[0] for r in rows if 그룹판정(r, m_그룹) == '일관 열세') or '-']
                for 분류, 뜻, rows, rho in sorted(res_그룹, key=lambda z: -(z[3] if z[3] == z[3] else -9))]
    li_그룹행 = [[분류 if j == 0 else '', r[0], f'{r[1]}', pc(r[2]), f'{r[3]}', pc(r[4]), f'{r[5]:.0f}%' if r[5] == r[5] else '-',
                (f'<span style="color:{GREEN}">★ {그룹판정(r, m_그룹)}</span>' if 그룹판정(r, m_그룹).startswith('일관') else 그룹판정(r, m_그룹))]
               for 분류, 뜻, rows, rho in res_그룹 for j, r in enumerate(rows)]
    그림_종목, rho_종목, li_종목, n_종목 = 종목지속(f_IS, f_OOS)
    li_종목행 = [[k, f'{n}', pc(a), f'{nb}', pc(b)] for k, n, a, nb, b in li_종목]

    # 거래별 그래프 (구분별 수익 중위 10 · 상위 10 · 하위 10 · 무작위 10)
    li_그림 = []
    for nm, df in (('OOS', x_OOS), ('IS', x_IS)):
        x = df.sort_values('수익', ascending=False).reset_index(drop=True)
        좋은, 나쁜 = x.iloc[:10], x.iloc[10:].iloc[::-1].iloc[:10]
        i_중 = max(0, len(x) // 2 - 5)
        중위 = x.iloc[i_중:i_중 + 10].drop(좋은.index.union(나쁜.index), errors='ignore')
        rest = x.drop(좋은.index.union(나쁜.index).union(중위.index))
        무작위 = rest.sample(min(10, len(rest)), random_state=0).sort_values(['일자', '진입초'])
        묶음 = [(f'수익 중위 10 (중앙값 {x.수익.median():+.2f}% 주변, 수익 높은 순)', 중위), ('수익 상위 10 (1위부터)', 좋은),
              ('수익 하위 10 (가장 나쁜 것부터)', 나쁜), ('무작위 10 (시각 순)', 무작위)]
        순위 = {**{k_: f'상위 {n + 1}위 ' for n, k_ in enumerate(좋은.index)}, **{k_: f'하위 {n + 1}위 ' for n, k_ in enumerate(나쁜.index)}}
        그림 = {}
        for s_일자, g in pd.concat([y for _, y in 묶음]).groupby('일자'):
            arr, codes = 적재(s_일자); idx = {cd: k for k, cd in enumerate(codes)}
            memo = {}
            for k_, r in g.iterrows():
                if r['코드'] not in memo:
                    memo[r['코드']] = 지표(arr[idx[r['코드']]])
                hh = T0 + int(r['진입초'])
                s_제목 = (f"{순위.get(k_, '')}{nm} {s_일자[4:6]}/{s_일자[6:]} {hh // 3600:02d}:{hh % 3600 // 60:02d}:{hh % 60:02d} {종목표시(r['코드'])}  "
                        f"{r['수익']:+.2f}% (비용 전 {r['비용전']:+.2f}%)  {int(r['청산초'] - r['진입초'])}초")
                그림[k_] = f'<div class="cell">{거래그래프(memo[r["코드"]], r, c, s_제목)}</div>'
        for s_묶음, y in 묶음:
            if len(y):
                li_그림.append(f'<h3>{nm} {s_묶음} {len(y)}건 · 거래당 {pc(y.수익.mean())}</h3><div class="grid">'
                              + ''.join(그림[k_] for k_ in y.index) + '</div>')

    css = f"""
:root{{--bg:{BG};--panel:{PANEL};--fg:{FG};--mut:{GRAY};--line:#30363d}}
body{{background:var(--bg);color:var(--fg);font-family:-apple-system,'Apple SD Gothic Neo',sans-serif;margin:0;padding:24px 16px;line-height:1.6}}
.wrap{{max-width:1200px;margin:0 auto}} h1{{font-size:24px;margin:0 0 4px}} h2{{font-size:19px;margin:36px 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}}
h3{{font-size:16px;margin:22px 0 8px}} .sub{{color:var(--mut);font-size:13px}} .pos{{color:{RED}}} .neg{{color:{BLUE}}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:16px 0}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 14px}} .card b{{font-size:21px;display:block}}
.tw{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0}} th,td{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:right;white-space:nowrap}}
th{{color:var(--mut);font-weight:600}} td:first-child,th:first-child{{text-align:left}} table.left td{{text-align:left;white-space:normal}}
img{{max-width:100%;border-radius:6px}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:10px}}
.cell{{background:var(--panel);border-radius:6px;padding:4px}}
@media (max-width:600px){{.grid{{grid-template-columns:1fr}}}}
"""
    # 격자 - 행 (이평 짝 · 60초 고저폭 · 손절) · 열 돌파 호가, 칸마다 비용 전 거래당 IS / OOS · 하루 건수 · 애매한 거래 비율
    li_격자, li_애매, dic_행 = [], [], {}
    for c_ in LI_칸:                                                    # 행 = 호가를 뺀 칸 이름 · 열 = 돌파 호가
        if c_['id'] == 'v1':
            continue
        s_행 = c_['행'] if c_['행'] != '-' else f"고저폭 ≥ {c_['고저폭']}% · 제외 {DIC_제외이름.get(c_['제외'], c_['제외'])}"
        si, so = s_IS.loc[c_['id']], s_OOS.loc[c_['id']]
        dic_행.setdefault(s_행, {})[c_['호가']] = f"{pc(si.비용전, 3)} / {pc(so.비용전, 3)}<br><span class='sub'>하루 {si.하루:,.0f} / {so.하루:,.0f}건 · 실측 {si.수익:+.2f} / {so.수익:+.2f}%</span>"
        for nm, s_ in (('IS', si), ('OOS', so)):
            li_애매.append([f"+{c_['호가']}호가 · {s_행}" if nm == 'IS' else '', nm, f'{s_.하루:,.1f}',
                          f'{s_.애매:.0f}%', pc(s_.애매평균, 3), f'{s_.위1:.1f}% / {s_.아래1:.1f}%', pc(s_.밖평균), pc(s_.비용전, 3)])
    li_격자 = [[k_] + [v_.get(h, '-') for h in LI_호가] for k_, v_ in dic_행.items()]
    # v12 시간대별 - 칸마다 시간대 비용 전 거래당 IS / OOS (괄호 건수)
    li_시간 = []
    if 원장 is not None:
        t_IS, t_OOS = 시간대(원장[0]), 시간대(원장[1])
        for c_ in LI_칸:
            li_시간.append([c_['이름']] + [f"{pc(a[1])} / {pc(b[1])}<br><span class='sub'>{a[0]} / {b[0]}건</span>" for a, b in zip(t_IS[c_['id']], t_OOS[c_['id']])])
    # v11 대기 격자 - 행 대기 초 · 열 손실 기준 (첫 호가·고저폭·제외 칸에서), 칸마다 비용 전 IS / OOS
    li_대기행, li_대기효과 = [], []
    if len(LI_대기) > 1:
        h0, g0, x0, (a0, b0) = LI_호가[-1], LI_고저폭[0], LI_제외[0], LI_이평[0]
        id_ = lambda wk: f'호가{h0}|고저폭{g0}|손절0|제외{x0}|대기{wk[0]}_{wk[1]:g}|이평{a0}_{b0}'
        ws, ks = sorted({w for w, _ in LI_대기 if w}), sorted({k for w, k in LI_대기 if w})
        si, so = s_IS.loc[id_((0, 0))], s_OOS.loc[id_((0, 0))]
        li_대기행.append(['대기 없음 (v10)'] + [f"{pc(si.비용전, 3)} / {pc(so.비용전, 3)}" if j == 0 else '' for j in range(len(ks))])
        for w in ws:
            row = [f'{w}초']
            for k in ks:
                si, so = s_IS.loc[id_((w, k))], s_OOS.loc[id_((w, k))]
                row.append(f"{pc(si.비용전, 3)} / {pc(so.비용전, 3)}<br><span class='sub'>실측 {si.수익:+.2f} / {so.수익:+.2f}%</span>")
            li_대기행.append(row)
        if 대기표 is not None:
            for (_, ri), (_, ro) in zip(대기표[0].iterrows(), 대기표[1].iterrows()):
                li_대기효과.append([f"대기 {ri.대기}초 · 기준 −{ri.기준:g}%", f'{ri.바뀜:.0f} / {ro.바뀜:.0f}%', f'{pc(ri.바뀐평균)} / {pc(ro.바뀐평균)}',
                                  f'{pc(ri.없었으면)} / {pc(ro.없었으면)}', f'{ri.좋아짐:.0f} / {ro.좋아짐:.0f}%', f'{ri.대기손실:.0f} / {ro.대기손실:.0f}%',
                                  f'{ri.보유:.0f} / {ro.보유:.0f}초', f'{pc(ri.변화, 3)} / {pc(ro.변화, 3)}'])
    li_손절 = []
    if 손절표 is not None:
        for (_, ri), (_, ro) in zip(손절표[0].iterrows(), 손절표[1].iterrows()):
            li_손절.append([f"+{ri.호가}호가 · 손절 {ri.손절:g}%", f'{ri.손절비율:.0f} / {ro.손절비율:.0f}%', f'{pc(ri.손절평균)} / {pc(ro.손절평균)}',
                          f'{pc(ri.없었으면)} / {pc(ro.없었으면)}', f'{ri.회복:.0f} / {ro.회복:.0f}%', f'{ri.더깊음:.0f} / {ro.더깊음:.0f}%',
                          f'{pc(ri.변화, 3)} / {pc(ro.변화, 3)}'])
    html = f"""<title>이평돌파 {S_버전}</title><style>{css}</style><div class="wrap">
<h1>이평돌파 {S_버전}</h1>
<div class="sub">{pd.Timestamp.now():%Y-%m-%d} · 틱 {len(li_전체)}거래일 ({min(li_전체)[4:6]}/{min(li_전체)[6:]} ~ {max(li_전체)[4:6]}/{max(li_전체)[6:]}) · 감시종목 하루 100~200개 · 1초 단위 재현 · 분석 전용(실매매 미연결)</div>
<div class="cards">
<div class="card">기준 칸 (그래프·그룹 분석)<b style="font-size:15px">{c['이름']}</b>사전 고정 (IS 에서 고르지 않음)</div>
<div class="card">IS {len(li_IS)}일 · {i.건수:,.0f}건 · 실측 순수익<b>{pc(i.수익)}</b>비용 전 {pc(i.비용전)} · 승률 {i.승률:.0f}% · 이익일 {i.이익일:.0f}/{i.일수:.0f}</div>
<div class="card">OOS {len(li_OOS)}일 · {o.건수:,.0f}건 · 실측 순수익<b>{pc(o.수익)}</b>비용 전 {pc(o.비용전)} · 승률 {o.승률:.0f}% · 이익일 {o.이익일:.0f}/{o.일수:.0f}</div>
<div class="card">통과 문턱 (IS·OOS 양쪽)<b style="font-size:15px">비용 전 ≥ +{N_문턱비용전}% · 실측 ≥ +{N_문턱실측}%</b>IS {통과(i)} · OOS {통과(o)}</div>
</div>

<h2>1. 로직 정의</h2>
{table(['조건', '지표', '뜻'], left=True, rows=[
    ['① 가격 이평 돌파', f"짧은 / 긴 이평 = 1초 종가의 이동평균 (거래 시간 축), 짝은 격자 {' · '.join(f'{a_}/{b_}초' for a_, b_ in LI_이평)}", '짧은 이평이 긴 이평을 위로 뚫은 초(직전 거래 초엔 짧은 ≤ 긴)부터 짧은 > 긴 이 이어지는 동안을 한 구간으로 본다. 그 구간에서 1초 종가가 돌파 초 종가보다 N 호가 이상 높고(호가 단위는 돌파 초 종가 기준) ②③ 이 함께 켜진 첫 초에 산다 (구간마다 1번, 시간 제한 없음 - v2~v4 의 돌파 후 5초 창은 뺐다). 장 시작 직후처럼 돌파 없이 시작된 구간은 쓰지 않는다'],
    ['① 돌파 호가', f"1초 종가 − 돌파 초 종가 ≥ N × 호가 단위", f"격자 {' / '.join(map(str, LI_호가))} 호가 (v4 의 3호가에서 늘려 확인을 세게)"],
    ['② 체결횟수', '체결횟수(초당, 1·2주 단주 제외)의 5초 / 30초 이동평균 (거래 시간 축)', f'5초 이평 ≥ {N_체결횟수5}회 그리고 5초 이평 > 30초 이평 (v2 에서 문턱을 뺐더니 하루 2.4만 건으로 잔물결 돌파가 다 들어와 되살렸다)'],
    ['③ 체결강도', '5초 체결강도 = 직전 5초 매수량 ÷ 매도량 × 100 (단주 제외, 거래 시간 축)', f'≥ {N_체결강도5} (100 = 매수·매도 같음, 매도가 없으면 999)'],
    ['④ 직전 60초 고저폭 (v6)', '직전 60초(시계 초, 그 초 포함) 1초 고가 최고 ÷ 1초 저가 최저 − 1 (%)', (f"≥ {LI_고저폭[0]}% 고정 (v6 격자 조건 없음 / 1 / 2 / 3 / 4% 에서 OOS 정점)" if len(LI_고저폭) == 1 else f"격자 {' / '.join('조건 없음' if g == 0 else f'≥ {g}%' for g in LI_고저폭)}") + f" - v5 수익·손실 분석에서 결과가 ±1% 밖으로 크게 갈릴 거래를 가장 잘 가른 값 (방향은 못 가름). 경계는 둥근 값으로만 둔다"],
    ['청산', '짧은 이평 ≤ 긴 이평 (진입에 쓴 짝)', '하향 돌파하는 첫 거래 초의 종가로 판다. 익절·최대 보유 없음, 15:15 강제 청산'],
    ['⑤ 제외 조건 (v9)', '횟수비 = 체결횟수 5초 이평 ÷ 30초 이평 · 횟수배수 = 체결횟수 30초 이평 ÷ 직전 5분 전~31초 전(시계) 초당 체결횟수 평균 · 평소 가격변동 = 5분 전~1분 전 가격이 바뀐 초 비율',
     f"①~④ 가 처음 모두 켜진 초에 하나라도 걸리면 그 위 구간은 건너뛴다 (조건이 풀리는 뒤 초로 미뤄 사면 끝물에 더 비싸게 산다): 횟수비 ≥ {N_횟수비상한} (체결이 갑자기 터진 끝물) · 횟수배수 ≥ {N_횟수배수상한} (평소보다 갑자기 붐빔) · 평소 가격변동 < {N_변동하한}% (거래가 뜸한 종목). v5 수익·손실 분석에서 IS·OOS·장 시작 10분 뒤에도 거래당을 일관되게 가른 셋, 경계는 둥근 값. 격자 = 없음 / 하나씩 / 3종 모두"],
    ['⑥ 당일 누적 거래대금 (v12)', '진입 초까지 그 종목의 당일 누적 거래대금 (억원, 체결틱의 누적거래대금)', f"격자 {' / '.join('조건 없음' if not u else f'< {u}억' for u in LI_대금)} - v10 거래 분석에서 작을수록 애매한 거래가 적고 거래당이 높았다 (시각과 상관 0.4)"],
    ['⑦ 분봉 3분 수익률 (v12)', '진입 분 바로 앞 완결 시계 분봉 종가 ÷ 그 3분 전 분봉 종가 − 1 (%) - 1초 캐시로 만든 분봉, 09:04 전에는 값 없음', f"격자 {' / '.join('조건 없음' if r is None else f'> {r:g}%' for r in LI_분수익)} - v10 거래 분석에서 분봉 항목 중 거래당을 IS·OOS 둘 다 가른 유일한 항목"],
    ['청산 대기 (v11)', '하향 돌파 초의 종가 vs 매수가 × (1 − 기준%)', f"하향 돌파 초의 종가가 기준선보다 위면(손실이 기준보다 얕으면) 바로 팔지 않고 N초 기다린다. 그 사이 짧은 이평이 다시 위로 올라오면 계속 보유(다음 하향 돌파에서 같은 규칙), 1초 저가가 기준선에 닿으면 그 초에 min(기준선, 종가) 로 판다, N초가 지나도 아래면 그때 종가로 판다. 격자 기준 {' / '.join(f'{k:g}' for k in sorted({k for w, k in LI_대기 if w}))}% × 대기 {' / '.join(str(w) for w in sorted({w for w, _ in LI_대기 if w}))}초 + 대기 없음"],
    ['청산 손절 (v8)', '손절선 = 매수가(신호 초 종가 × 1.0014) × (1 − N%)', f"하향 돌파 전에 1초 저가가 손절선에 닿으면 그 초에 min(손절선, 그 초 종가) 로 판다 (같은 초에 하향 돌파도 걸리면 손절이 먼저). " + ('v8 격자 0.5 / 1 / 1.5 / 2 / 3% 가 모두 거래당을 깎아 v9 부터 쓰지 않는다' if LI_손절 == [0] else f"격자 {' / '.join('없음' if not v else f'{v:g}%' for v in LI_손절)}")],
    ['공통', '-', f"09:01 ~ 15:10 진입 · 가격 1,000원 이상 · 거래 정지가 풀린 뒤 {N_정지후금지}초 동안 진입 안 함 · 같은 종목 재진입은 다음 상향 돌파부터"],
    ['거래 시간', '정지 구간·첫 체결 전을 뺀 초', f"모든 이평·창은 이 축에서 센다. 정지 추정 = 체결 없음 {N_정지최소초}초 이상 + 직전 30초 {N_정지직전건수}건 이상. 정지 중에는 판정하지 않는다"],
])}
<h3>칸</h3>
<p>격자 누적 대금 {len(LI_대금)} × 3분 수익 {len(LI_분수익)} × 청산 대기 {len(LI_대기)} × 제외 방식 {len(LI_제외)} × 손절 {len(LI_손절)} × 돌파 호가 {len(LI_호가)} (60초 고저폭 {' / '.join(f'{g}%' for g in LI_고저폭)} · 이평 {' / '.join(f'{a_}/{b_}초' for a_, b_ in LI_이평)}) = {len(LI_칸) - 1}칸 + 비교용 v1 기준 (5/30 · 호가·고저폭·제외 조건 없음 · 체결횟수 5초 ≥ {N_체결횟수5} 만). 기준 칸({c['이름']})은 미리 정해 두고, 그래프와 그룹 분석은 이 칸으로 그린다.</p>

<h2>2. 검증 설계</h2>
{table(['항목', '내용'], left=True, rows=[
    ['일자 분할', f'무작위 반반 (씨앗값 {N_분할씨앗}) — 시간순이 아니다. {S_봉인시작[4:6]}/{S_봉인시작[6:]} 부터는 전진검증용으로 남겨 두고 쓰지 않는다'],
    [f'IS {len(li_IS)}일', ', '.join(f'{x[4:6]}/{x[6:]}' for x in li_IS)],
    [f'OOS {len(li_OOS)}일', ', '.join(f'{x[4:6]}/{x[6:]}' for x in li_OOS)],
    ['체결·비용 (실측)', f'매수 = 신호 초 종가 × (1 + {N_실측매수}%) · 매도 = 청산 초 종가 × (1 − {N_실측매도}%) · 세금·수수료 {N_실측비용}% → 왕복 약 {n_비용:.2f}% (2026-10-30 실매매 400건 실측)'],
    ['비용 전', '청산 초 종가 ÷ 신호 초 종가 − 1. 비용과 상관없이 신호에 방향성이 있는지만 본다'],
    ['통과 문턱', f'비용 전 ≥ +{N_문턱비용전}% 그리고 실측 순수익 ≥ +{N_문턱실측}% 를 IS·OOS 양쪽에서 (2026-10-30 수익 구멍 점검 때 정한 기준)'],
    ['일 단위 신뢰구간', '날짜를 다시 뽑는 부트스트랩 95% 구간 (같은 날 거래끼리 묶여 움직이므로 거래 단위보다 넓다)'],
])}

<h2>3. 칸 비교</h2>
{'' if not li_대기행 else f'''<h3>청산 대기 격자 — 비용 전 거래당 IS / OOS (행 대기 초 · 열 손실 기준)</h3>
{table(['대기'] + [f'기준 −{k:g}%' for k in sorted({k for w, k in LI_대기 if w})], li_대기행)}
<h3>대기가 한 일 — 대기 때문에 청산이 바뀐 거래 (IS / OOS)</h3>
<p>진입은 대기와 상관없이 같으므로 같은 거래를 '대기 없음' 칸과 짝지었다. '바뀐 거래'는 청산 초가 달라진 거래, '대기 중 기준선 닿음'은 기다리다 손실 기준에 닿아 판 거래다.</p>
{table(['칸', '바뀐 거래 비율', '바뀐 거래 평균 (비용 전)', '대기 없었으면', '좋아진 비율', '대기 중 기준선 닿음', '보유 중앙값', '거래당 변화'], li_대기효과)}'''}
<h3>격자 — 비용 전 거래당 IS / OOS</h3>
{table(['칸'] + [f'+{h}호가' for h in LI_호가], li_격자)}
{'' if not li_시간 else f'''<h3>시간대별 — 비용 전 거래당 IS / OOS (아래 숫자는 건수)</h3>
<p>진입 시각으로 나눴다. 칸마다 IS·OOS 가 같은 시간대에서 같이 좋거나 나쁜지 본다 - 장 시작 효과가 평균을 끌어올리는지 확인하는 표.</p>
{table(['칸'] + [nm for _, _, nm in LI_시간대], li_시간)}'''}
{'' if not li_손절 else f'''<h3>손절이 한 일 — 손절로 끊은 거래가 손절이 없었으면 (IS / OOS)</h3>
<p>진입은 손절과 상관없이 같으므로 같은 거래를 '손절 없음' 칸과 짝지었다. 손절선이 얕을수록 많이 끊지만, 끊은 거래 중 손절이 없었으면 플러스로 돌아왔을 거래(회복)도 많아진다.
'거래당 변화'는 전체 거래의 비용 전 거래당이 손절로 얼마나 바뀌었나 (+ 면 손절이 도움).</p>
{table(['칸', '손절 비율', '손절 거래 평균 (비용 전)', '손절 없었으면', '손절 없었으면 플러스로 끝남', '손절 없었으면 더 깊게 끝남', '거래당 변화'], li_손절)}'''}
<h3>애매한 거래가 얼마나 빠지나</h3>
<p>애매한 거래 = 비용 전 수익이 ±{N_애매:g}% 안. 지금 청산(하향 돌파)으로 끝난 결과 기준이다. ±{N_애매:g}% 밖 비율이 늘어도 + 쪽과 − 쪽이 같이 늘면 거래당은 나아지지 않는다.</p>
{table(['칸', '구분', '하루 건수', '애매한 거래 비율', '애매한 거래 평균', f'+{N_애매:g}% 이상 / −{N_애매:g}% 이하', f'±{N_애매:g}% 밖 거래 평균', '비용 전 거래당'], li_애매)}
<h3>칸별 상세</h3>
{table(['칸', '구분', '건수', '하루 건수', '비용 전 거래당', '비용 전 일 단위 95%', '실측 순수익', '승률', '비용 전 승률', '보유 중앙값', '이익일', '문턱'], li_칸)}

<h2>4. 돌파 뒤에 상승이 이어지는가 — 신호 후 평균 가격 경로</h2>
{경로그림(경로)}
<p>기준 규칙의 진입 초를 0초로 두고 그 전후 가격을 진입 초 종가 대비 %로 평균했습니다(띠는 가운데 50%). 회색 점선(실측 비용 {n_비용:.2f}%)을 넘어야 비용을 제하고 남고, 초록 점선({N_문턱비용전}%)이 통과 문턱입니다.</p>

<h2>5. 기준 규칙 성적</h2>
{table(['구분', '건수', '비용 전 거래당', '실측 순수익', '중앙값', '승률', '보유 중앙값', '거래일', '청산 사유'], li_구분)}
<h3>수익률 분포</h3>
<p>실측 비용을 뺀 순수익률을 0.25% 단위로 세었습니다. 빨강 = 수익, 파랑 = 손실, 초록선 = 손익 0, 흰 점선 = 평균. 양 끝 칸은 그 바깥 거래를 모두 합친 값입니다.</p>
{분포그림(x_IS.수익, x_OOS.수익)}
<h3>보유 시간별</h3>
<p>하향 돌파로 금방 나간 거래와 오래 간 거래의 비용 전 수익입니다. 흐린 막대가 IS, 진한 막대가 OOS 입니다.</p>
{보유그림(x_IS, x_OOS)}

<h2>6. 의미 있는 그룹이 있는가 — 시간·종목·시장 분류별 IS·OOS</h2>
<p>기준 규칙 거래 IS {len(f_IS):,}건(거래당 {pc(m_그룹[0])}) · OOS {len(f_OOS):,}건(거래당 {pc(m_그룹[1])})을 <b>진입 순간에 알 수 있는 값</b>으로 나눴습니다. 거래당은 실측 순수익입니다.
흐린 막대가 IS, 진한 막대가 OOS, 초록선 = 손익 0, 흰 점선 = 전체 거래당. ★ = IS·OOS 모두 {N_그룹최소}건 이상이고 둘 다 같은 방향으로 {N_그룹차이:.2f}%p 이상 벗어난 그룹.
5등분 경계는 IS 에서 정해 OOS 에 그대로 썼습니다. 그룹이 {sum(len(z[2]) for z in res_그룹)}개라 우연히 방향이 맞는 그룹도 몇 개는 나옵니다.</p>
{그룹그림(res_그룹, m_그룹)}
<h3>분류별 요약 (순위상관 높은 순)</h3>
{table(['분류', '뜻', 'IS·OOS 순위상관', '일관 우세 그룹', '일관 열세 그룹'], li_그룹요약)}
<h3>종목별 — IS 에서 좋던 종목이 OOS 에서도 좋은가</h3>
<p>IS·OOS 에서 각각 3건 이상 거래한 종목 {n_종목}개를 IS 거래당으로 3등분하고 같은 종목들의 OOS 성적을 봤습니다.</p>
{그림_종목}
{table(['IS 기준 묶음', '종목 수', 'IS 거래당', 'OOS 건수', 'OOS 거래당'], li_종목행)}
<h3>그룹별 상세</h3>
{table(['분류', '그룹', 'IS 건수', 'IS 거래당', 'OOS 건수', 'OOS 거래당', 'OOS 승률', '판정'], li_그룹행)}

<h2>7. 거래별 그래프</h2>
<p>위에서부터 ① 가격(흰색 1초 종가 · 노랑 짧은 이평 · 보라 긴 이평 · 노랑 점 상향 돌파 · 초록 점선 돌파 초 종가 +N호가 · 파랑 점선 손절선 · 매수 ▲ · 청산 ▼) / ② 체결횟수(초당, 단주 제외) 5초 이평(노랑)·30초 이평(보라), 초록 점선 = 문턱 /
체결량(주, 단주 포함, 회색 막대)과 5초·30초 이평 / 거래대금(백만원, 회색 막대)과 5초·30초 이평 / ③ 5초 체결강도(빨강, 로그 눈금)와 10초 체결강도(회색, 참고) / 호가 잔량비율(매수 ÷ 매도 총잔량, 10/12 부터) /
가격 추세(5초 이평이 직전 10초 중 오른 횟수 빨강·내린 횟수 파랑, 참고) / 평소 가격변동(5분 전~1분 전 가격이 바뀐 초 비율, 참고) / 조건 충족 띠(노랑)와 전부 충족(초록 - 상향 돌파 뒤 처음 켜지는 초가 진입).
회색 띠는 거래 정지 구간입니다. 제목의 수익은 실측 순수익, 괄호는 비용 전입니다.</p>
{''.join(li_그림)}
<div class="sub">재현: python analyzer/이평돌파.py · 1초 캐시 {{work}}/분석/백테스팅/이평돌파/_초캐시 · 거래 원장 {{work}}/분석/백테스팅/이평돌파/{S_버전}_거래_IS·OOS.pkl</div>
</div>"""
    return html


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', action='store_true')
    ap.add_argument('--no-telegram', action='store_true')
    ap.add_argument('--proc', type=int, default=N_병렬)
    a = ap.parse_args()
    N_병렬 = a.proc
    if a.cache:
        캐시보충(min(3, N_병렬))
    else:
        run(b_텔레그램=not a.no_telegram)

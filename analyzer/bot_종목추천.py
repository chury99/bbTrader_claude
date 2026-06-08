import os
import sys
import json
import time
import re

import pandas as pd
import dataframe_image as dfi
from tqdm import tqdm
from google import genai

import ut


# noinspection NonAsciiCharacters,SpellCheckingInspection,PyPep8Naming
class AnalyzerBot:
    # noinspection PyUnresolvedReferences
    def __init__(self):
        # config 읽어 오기
        self.folder_베이스 = os.path.dirname(os.path.abspath(__file__))
        self.folder_프로젝트 = os.path.dirname(self.folder_베이스)
        self.s_파일명 = os.path.basename(__file__).replace('.py', '')
        dic_config = ut.도구manager.ToolManager().config로딩()

        # 로그 설정
        log = ut.로그maker.LogMaker(s_파일명=self.s_파일명, s_로그명='로그이름_analyzer')
        sys.stderr = ut.로그maker.StderrHook(path_에러로그=log.path_에러)
        self.make_로그 = log.make_로그

        # 폴더 정의
        dic_폴더정보 = ut.폴더manager.FolderManager().dic_폴더정보
        self.folder_대상종목 = dic_폴더정보['데이터|대상종목']
        self.folder_조회순위 = dic_폴더정보['데이터|조회순위']
        self.folder_차트정보 = dic_폴더정보['데이터|차트정보']
        self.folder_분석 = dic_폴더정보['분석']
        os.makedirs(self.folder_분석, exist_ok=True)

        # 추가 폴더 정의
        dic_aikey = json.load(open(os.path.join(dic_config['folder_aikey'], 'aikey.json')))
        self.api키_gemini = dic_aikey.get('gemini', dict()).get('apikey', None)
        self.n_서버파일보관일수 = int(dic_config['파일보관기간(일)_analyzer'])

        # 기준정보 정의
        self.s_오늘 = pd.Timestamp.now().strftime('%Y%m%d')
        self.n_tr딜레이 = 0.2
        self.s_계좌번호 = str(dic_config['계좌번호'])

        # 사용 모듈 정의
        self.tool = ut.도구manager.ToolManager()

        # 키움 API 연결
        sys.path.append(dic_config['folder_kiwoom'])
        import RestAPI_kiwoom
        self.api = RestAPI_kiwoom.RestAPIkiwoom(s_계좌번호=self.s_계좌번호)

        # 카카오 API 연결
        sys.path.append(dic_config['folder_kakao'])
        import API_kakao
        self.kakao = API_kakao.KakaoAPI()

        # 로그 기록
        self.make_로그(f'구동 시작')

    def make_지표생성(self):
        """ 일봉 데이터 기반으로 지표 생성 후 저장 """
        # 기준정보 정의
        folder_소스 = self.folder_차트정보
        file_소스 = f'dic_일봉차트'
        folder_타겟 = os.path.join(self.folder_분석, '10_지표생성')
        file_타겟 = f'dic_지표생성'
        os.makedirs(folder_타겟, exist_ok=True)

        # 대상일자 확인
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스)
                         if file_소스 in 파일 and '.pkl' in 파일)
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                   if file_타겟 in 파일 and '.pkl' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

        # 일자별 매수매도 정보 생성
        for s_일자 in li_대상일자:
            # 소스파일 불러오기 - 조회순위 종목 기준의 일봉차트 데이터
            dic_일봉차트 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_일자}.pkl'))
            dic_코드2종목명 = {코드: 일봉['종목명'].values[0] for 코드, 일봉 in dic_일봉차트.items()}

            # 추가 데이터 불러오기
            df_분석대상 = pd.read_pickle(os.path.join(self.folder_대상종목, f'df_대상종목_{s_일자}.pkl'))

            # 대상종목 선정
            li_대상종목 = sorted(종목 for 종목 in dic_일봉차트.keys() if 종목 in df_분석대상['종목코드'].values)

            # 종목별 데이터 생성
            dic_지표생성 = dict()
            for s_종목코드 in tqdm(li_대상종목, desc=f'일봉차트-{s_일자}', file=sys.stdout):
                # 기준정보 정의
                df_일봉 = dic_일봉차트.get(s_종목코드, pd.DataFrame())
                if df_일봉.empty: continue

                # 지표 생성
                df_일봉['전일고가3봉'] = df_일봉['고가'].shift(1).rolling(window=3).max()
                df_일봉['돌파신호'] = df_일봉['종가'] > df_일봉['전일고가3봉']

                # df 추가
                dic_지표생성[s_종목코드] = df_일봉

                # df 저장
                folder = os.path.join(f'{folder_타겟}_종목별', f'지표생성_{s_일자}')
                os.makedirs(folder, exist_ok=True)
                df_일봉.to_csv(os.path.join(folder, f'df_지표생성_{s_일자}_{s_종목코드}_{dic_코드2종목명.get(s_종목코드, '')}.csv'),
                             index=False, encoding='cp949')

            # 결과 저장
            pd.to_pickle(dic_지표생성, os.path.join(folder_타겟, f'{file_타겟}_{s_일자}.pkl'))

            # 로그 기록
            self.make_로그(f'{s_일자} - {len(dic_지표생성):,.0f}종목')

    def pick_종목선정(self):
        """ 종목선정 기준에 따라 추천종목 선정 후 저장 """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_분석, '10_지표생성')
        file_소스 = f'dic_지표생성'
        folder_타겟 = os.path.join(self.folder_분석, '20_종목선정')
        file_타겟 = f'df_종목선정'
        os.makedirs(folder_타겟, exist_ok=True)

        # 대상일자 확인
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스)
                         if file_소스 in 파일 and '.pkl' in 파일)
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                   if file_타겟 in 파일 and '.pkl' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

        # 일자별 매수매도 정보 생성
        for s_일자 in li_대상일자:
            # 소스파일 불러오기 - 조회순위 종목 기준의 일봉차트 데이터
            dic_지표생성 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_일자}.pkl'))

            # 종목별 선정조건 확인
            li_dic종목선정 = list()
            for s_종목코드, df_일봉 in dic_지표생성.items():
                # 기준정보 정의
                dt_당일 = df_일봉.index[-1]
                n_당일시가 = df_일봉.loc[dt_당일, '시가']
                n_당일종가 = df_일봉.loc[dt_당일, '종가']
                n_전일종가 = df_일봉.loc[dt_당일, '전일종가']
                n_당일60 = df_일봉.loc[dt_당일, '종가ma60']
                n_당일120 = df_일봉.loc[dt_당일, '종가ma120']
                n_당일바디 = (n_당일종가 - n_당일시가) / n_전일종가 * 100

                # 선정조건 확인
                b_정배열 = n_당일종가 > n_당일60 > n_당일120
                b_돌파여부 = True in df_일봉['돌파신호'].values[-5:]
                b_눌림여부 = -2 < n_당일바디 < 5

                # 결과 생성
                dic_종목선정 = df_일봉.loc[dt_당일].to_dict()
                dic_종목선정.update(당일종가=n_당일종가, 당일60=n_당일60, 당일120=n_당일120, 당일바디=n_당일바디,
                                종목선정=(b_정배열 and b_돌파여부 and b_눌림여부), 정배열=b_정배열, 돌파여부=b_돌파여부, 눌림여부=b_눌림여부)
                li_dic종목선정.append(dic_종목선정)

            # 데이터 정리
            df_종목선정 = pd.DataFrame(li_dic종목선정) if len(li_dic종목선정) > 0 else pd.DataFrame()

            # 결과 저장
            self.tool.df저장(df=df_종목선정, path=os.path.join(folder_타겟, f'{file_타겟}_{s_일자}'))

            # 로그 기록
            n_전체종목수 = len(df_종목선정)
            n_선정종목수 = len(df_종목선정.loc[df_종목선정['종목선정']])
            self.make_로그(f'{s_일자} - {n_선정종목수:,.0f}/{n_전체종목수:,.0f}종목')

    # noinspection PyUnboundLocalVariable,RegExpRedundantEscape
    def make_우선순위(self):
        """ 선정된 추천종목 기준으로 확률정보 생성하여 우선순위 선정 """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_분석, '20_종목선정')
        file_소스 = f'df_종목선정'
        folder_타겟 = os.path.join(self.folder_분석, '30_우선순위')
        file_타겟 = f'df_우선순위'
        os.makedirs(folder_타겟, exist_ok=True)

        # 대상일자 확인
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스)
                         if file_소스 in 파일 and '.pkl' in 파일)
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                   if file_타겟 in 파일 and '.pkl' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

        # 일자별 매수매도 정보 생성
        for s_일자 in li_대상일자:
            # 소스파일 불러오기 - 조회순위 종목 기준의 일봉차트 데이터
            df_종목선정 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_일자}.pkl'))
            li_대상종목 = df_종목선정.loc[df_종목선정['종목선정'], '종목코드'].to_list()

            # 일봉 불러오기 - 추가지표 포함된 데이터
            dic_지표생성 = pd.read_pickle(os.path.join(self.folder_분석, '10_지표생성', f'dic_지표생성_{s_일자}.pkl'))
            dic_일봉 = {종목코드: 일봉 for 종목코드, 일봉 in dic_지표생성.items() if 종목코드 in li_대상종목}

            # ai 기준정보 정의 - 제미나이
            client = genai.Client(api_key=self.api키_gemini)
            # s_모델 = 'gemini-2.5-flash'
            s_모델 = 'gemini-3-flash-preview'
            # s_모델 = 'gemini-3.1-flash-lite-preview'

            # 상승확률 계산 - 반복 진행
            li_dic응답 = list()
            for _ in tqdm(range(10), desc=f'AI분석({s_모델})-{s_일자}', file=sys.stdout):
                # 제미나이 cli 적용
                s_질문 = ('너는 일 단위의 단기 매매를 전문으로 하는 주식 퀀트 분석 전문가야.\n'
                        '투자의 기본 틀은 +10% 이상 시 익절, -3% 이하 시 손절하는 방식이야.\n'
                        '아래 종목들은 오늘 장 마감 기준 내일 상승할 여력이 있는 후보 종목들인데,\n'
                        '각 종목의 캔들 패턴, 거래량 변화, 추세 형성 패턴 등을 분석해서\n'
                        '오늘 종가 대비 내일 고가가 +10% 이상 상승할 확률을 계산해줘. 단, 10% 상승하기 이전에 -3% 밑으로 내려가면 안돼.\n'
                        '분석의 중요도는 추세 돌파 가능성, 캔들의 상승패턴 형성, 거래량 집중의 우선순위로 분석해줘.'
                        '\n'
                        '응답은 다른 말은 하지말고 반드시 아래 json 구조를 지켜주고, 단위는 표기하지 말아줘.\n'
                        ' : {"종목코드" : {"종목명" : "종목명", "상승확률" : "확률숫자", "이유" : "이유"}}\n'
                        '\n'
                        '대상 종목은 아래와 같아.\n'
                        f' : {li_대상종목}\n'
                        f'\n'
                        '대상 종목의 일봉 정보는 아래와 같아. 약 120일 전부터 오늘까지의 일봉 데이터야. 마지막 일자 이후의 상승 확률을 구하면 돼.\n'
                        f' : {dic_일봉}\n'
                        f'\n'
                        '차트 데이터를 읽을 때 날짜 혼동하지 말고, 등락률 정확히 파악해서 결과에 혼선을 주지 않도록 해.')
                time.sleep(10)

                # 제미나이 요청 - 서버 과부하 시 3회 반복
                for _ in range(3):
                    try:
                        res = client.models.generate_content(model=s_모델, contents=s_질문)
                        break
                    except Exception as e:
                        if '503' not in str(e): raise
                        time.sleep(10)

                # 데이터 정리
                match = re.search(r'```json\n(.*?)\n```', res.text, re.DOTALL)
                s_응답내용 = match.group(1) if match else re.search(r'\{.*\}', res.text, re.DOTALL).group(0)
                dic_응답 = json.loads(s_응답내용)
                li_dic응답.append(dic_응답)

            # 최종 확률 산정 - 10회 중 best, worst 각 2개씩 제외한 6개 값의 평균
            dic_상승확률 = li_dic응답[-1]
            for s_종목코드 in dic_상승확률.keys():
                li_확률 = [int(dic_응답.get(s_종목코드, dict()).get('상승확률', 0)) for dic_응답 in li_dic응답]
                li_확률_대상 = sorted(li_확률)[2: -2]
                dic_상승확률[s_종목코드]['상승확률'] = int(sum(li_확률_대상) / len(li_확률_대상)) if len(li_확률_대상) > 0 else 0

            # 결과 정리
            df_우선순위 = df_종목선정.loc[df_종목선정['종목선정'], ['일자', '종목코드', '종목명']].copy()
            df_우선순위['상승확률'] = [int(dic_상승확률[종목코드]['상승확률']) for 종목코드 in df_우선순위['종목코드']]
            df_우선순위['상승이유'] = [dic_상승확률[종목코드]['이유'] for 종목코드 in df_우선순위['종목코드']]
            df_우선순위['ai모델'] = s_모델
            df_우선순위 = df_우선순위.sort_values('상승확률', ascending=False).reset_index(drop=True)

            # 결과 저장
            self.tool.df저장(df=df_우선순위, path=os.path.join(folder_타겟, f'{file_타겟}_{s_일자}'))

            # 로그 기록
            self.make_로그(f'{s_일자} - {len(df_우선순위):,.0f}종목')

    def send_종목알림(self):
        """ 선정된 추천종목을 서버에 저장 및 카톡 알림 """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_분석, '20_종목선정')
        file_소스 = f'df_종목선정'
        folder_타겟 = os.path.join(self.folder_분석, '40_종목알림')
        file_타겟 = f'종목알림'
        os.makedirs(folder_타겟, exist_ok=True)

        # 대상일자 확인
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스)
                         if file_소스 in 파일 and '.pkl' in 파일)
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                   if file_타겟 in 파일 and '.png' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

        # 일자별 매수매도 정보 생성
        for s_일자 in li_대상일자:
            # 소스파일 불러오기 - 조회순위 종목 기준의 일봉차트 데이터
            df_종목선정 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_일자}.pkl'))

            # 종목알림 선정
            df_종목알림 = df_종목선정.loc[df_종목선정['종목선정'], ['일자', '종목코드', '종목명']].copy().reset_index(drop=True)

            # df를 이미지로 저장
            df_스타일 = (df_종목알림.style
                      .set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}])
                      .set_properties(subset=['종목명'], **{'text-align': 'left'})
                      )
            s_파일명 = f'{file_타겟}_{s_일자}.png'
            dfi.export(df_스타일, os.path.join(folder_타겟, s_파일명), dpi=300)

            # 서버에 저장
            s_서버폴더 = '종목추천'
            li_복사한파일명, li_삭제한파일명, dic_서버정보 = self.tool.sftp파일업로드(
                            folder_로컬=folder_타겟, s_서버폴더=s_서버폴더, s_파일명=s_파일명, n_파일보관일수=self.n_서버파일보관일수)

            # 메세지 송부
            if s_일자 == li_대상일자[-1]:
                # 메세지 생성
                s_메세지 = f'## [{s_일자}] 추천종목 {len(df_종목알림)}개 ##'
                for idx in df_종목알림.index:
                    s_종목명 = df_종목알림.loc[idx, '종목명']
                    s_종목코드 = df_종목알림.loc[idx, '종목코드']
                    s_메세지 = s_메세지 + f'\n  {s_종목명}({s_종목코드})'

                # 카톡 송부
                s_url주소 = f'http://{dic_서버정보['sftp']['hostname']}/kakao/{s_서버폴더}'
                self.kakao.send_메세지(s_사용자='알림봇', s_수신인='여봉이', s_메세지=s_메세지,
                                    s_버튼이름=f'추천종목 사유', s_연결url=f'{s_url주소}/{s_파일명}')

            # 로그 기록
            self.make_로그(f'{s_일자} - {len(df_종목알림):,.0f}종목')

    def send_종목알림with제미나이(self):
        """ 선정된 추천종목을 서버에 저장 및 카톡 알림 """
        # 기준정보 정의
        folder_소스 = os.path.join(self.folder_분석, '30_우선순위')
        file_소스 = f'df_우선순위'
        folder_타겟 = os.path.join(self.folder_분석, '40_종목알림')
        file_타겟 = f'종목알림'
        os.makedirs(folder_타겟, exist_ok=True)

        # 대상일자 확인
        li_전체일자 = sorted(re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_소스)
                         if file_소스 in 파일 and '.pkl' in 파일)
        li_완료일자 = [re.findall(r'\d{8}', 파일)[0] for 파일 in os.listdir(folder_타겟)
                   if file_타겟 in 파일 and '.png' in 파일]
        li_대상일자 = [일자 for 일자 in li_전체일자 if 일자 not in li_완료일자]

        # 일자별 매수매도 정보 생성
        for s_일자 in li_대상일자:
            # 소스파일 불러오기 - 조회순위 종목 기준의 일봉차트 데이터
            df_우선순위 = pd.read_pickle(os.path.join(folder_소스, f'{file_소스}_{s_일자}.pkl'))

            # df를 이미지로 저장
            df_스타일 = (df_우선순위.style
                      .set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}])
                      .set_properties(subset=['종목명', '상승이유'], **{'text-align': 'left'})
                      .set_properties(subset=['상승확률'], **{'text-align': 'center'})
                      )
            s_파일명 = f'{file_타겟}_{s_일자}.png'
            dfi.export(df_스타일, os.path.join(folder_타겟, s_파일명), dpi=300)

            # 서버에 저장
            s_서버폴더 = '종목추천'
            li_복사한파일명, li_삭제한파일명, dic_서버정보 = self.tool.sftp파일업로드(
                            folder_로컬=folder_타겟, s_서버폴더=s_서버폴더, s_파일명=s_파일명, n_파일보관일수=self.n_서버파일보관일수)

            # 메세지 송부
            if s_일자 == li_대상일자[-1]:
                # 메세지 생성
                s_메세지 = f'## [{s_일자}] 추천종목 {len(df_우선순위)}개 ##'
                for idx in df_우선순위.index:
                    s_종목명 = df_우선순위.loc[idx, '종목명']
                    s_종목코드 = df_우선순위.loc[idx, '종목코드']
                    n_상승확률 = df_우선순위.loc[idx, '상승확률']
                    s_메세지 = s_메세지 + f'\n  {n_상승확률}%-{s_종목명}({s_종목코드})'
                s_메세지 = s_메세지 + f'\n[ {df_우선순위['ai모델'].values[0]} ]'

                # 카톡 송부
                s_url주소 = f'http://{dic_서버정보['sftp']['hostname']}/kakao/{s_서버폴더}'
                self.kakao.send_메세지(s_사용자='알림봇', s_수신인='여봉이', s_메세지=s_메세지,
                                    s_버튼이름=f'추천종목 사유', s_연결url=f'{s_url주소}/{s_파일명}')

            # 로그 기록
            self.make_로그(f'{s_일자} - {len(df_우선순위):,.0f}종목')


# noinspection PyPep8Naming,NonAsciiCharacters,SpellCheckingInspection
def timer_실행지연(s_실행시간):
    dt_실행시각 = pd.Timestamp(s_실행시간)
    while pd.Timestamp.now() < dt_실행시각:
        s_잔여시간 = str(dt_실행시각 - pd.Timestamp.now()).split()[-1].split('.')[0]
        s_화면출력 = (f'\r[{pd.Timestamp.now().strftime('%H:%M:%S')}]'
                  f' 종목알림 예정({s_실행시간}) - {s_잔여시간} 후 실행')
        print(s_화면출력, end='', flush=True)
        time.sleep(1)

# noinspection PyPep8Naming,SpellCheckingInspection,NonAsciiCharacters
def run():
    """ 실행 함수 """
    a = AnalyzerBot()
    a.make_지표생성()
    a.pick_종목선정()
    # a.make_우선순위()
    timer_실행지연(s_실행시간='16:00:00')
    # a.send_종목알림with제미나이()
    a.send_종목알림()


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print('\n### [ KeyboardInterrupt detected ] ###')

import os
import sys
import re

import pandas as pd
import sqlite3
import json
import paramiko
from pandas.core.methods.selectn import SelectNSeries


# noinspection NonAsciiCharacters,PyPep8Naming,SpellCheckingInspection,PyUnreachableCode
class ToolManager:
    def __init__(self):
        # 기준폴더 정의
        self.folder_베이스 = os.path.dirname(os.path.abspath(__file__))
        self.folder_프로젝트 = os.path.dirname(self.folder_베이스)

        # 구동 os 확인
        dic_운영체제 = dict(darwin='mac', win32='win', linux='linux')
        self.s_운영체제 = dic_운영체제[sys.platform]

    def config로딩(self):
        """ config.json 파일 확인 후 구동 중인 환경에 맞도록 변수 정의 """
        # config 읽어 오기
        dic_config = json.load(open(os.path.join(self.folder_프로젝트, 'config.json'), mode='rt', encoding='utf-8'))

        # 대상항목 확인
        li_대상항목 = [항목 for 항목 in dic_config.keys() if type(dic_config[항목]) == dict]

        # config 정의
        for s_대상항목 in li_대상항목:
            dic_config[s_대상항목] = dic_config[s_대상항목][self.s_운영체제]

        return dic_config

    @staticmethod
    def df저장(df, path, li_타입=None):
        """ 입력받은 df를 path에 pkl, csv로 저장 """
        # 저장타입 지정
        li_타입 = ['pkl', 'csv'] if li_타입 is None else li_타입

        # pkl 저장
        if 'pkl' in li_타입:
            path_pkl = f'{path}.pkl'
            df.to_pickle(path_pkl)

        # csv 저장
        if 'csv' in li_타입:
            path_csv = f'{path}.csv'
            df.to_csv(path_csv, encoding='cp949', index=False)

    @staticmethod
    def sql불러오기(path, s_테이블명=None, b_전체=False):
        """ sql 파일을 불러와서 테이블명, 데이터 리턴 """
        # 파일 연결
        con = sqlite3.connect(path)

        # 전체 데이터 불러오기
        if b_전체:
            df_테이블명 = pd.read_sql(f'SELECT name FROM sqlite_master WHERE type="table"', con=con)
            dic_데이터 = dict()
            for s_테이블명 in df_테이블명['name']:
                dic_데이터[s_테이블명] = pd.read_sql(f'SELECT * FROM {s_테이블명}', con=con)

            return dic_데이터

        # 테이블명 불러오기
        elif s_테이블명 is None:
            df_테이블명 = pd.read_sql(f'SELECT name FROM sqlite_master WHERE type="table"', con=con)
            li_테이블명 = list(df_테이블명['name'])
            con.close()

            return li_테이블명

        # 데이터 불러오기
        elif s_테이블명 is not None:
            df_데이터 = pd.read_sql(f'SELECT * FROM {s_테이블명}', con=con)
            con.close()

            return df_데이터

        else:
            con.close()
            return None


    def sftp_동기화_파일명(self, folder_로컬, folder_서버, s_모드, s_기준일=None):
        """ sftp 서버 접속 후 파일명 기준으로 동기화 """
        # 서버정보 정의
        dic_서버정보 = json.load(open(os.path.join(self.folder_프로젝트, 'server_info.json'), mode='rt', encoding='utf-8'))
        dic_서버접속 = dic_서버정보['sftp']
        dic_서버폴더 = dic_서버정보['folder']

        # 서버 접속
        li_동기화파일명 = list()
        with (paramiko.SSHClient() as ssh):
            # ssh 서버 연결 (알수없는 서버 경고 방지 포함)
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostname=dic_서버접속['hostname'], port=dic_서버접속['port'],
                        username=dic_서버접속['username'], password=dic_서버접속['password'])

            # sftp 세션 시작
            with ssh.open_sftp() as sftp:
                # 폴더 내 파일 확인
                li_로컬파일 = sorted(파일 for 파일 in os.listdir(folder_로컬) if not 파일.startswith('.'))
                li_서버파일 = sorted(파일 for 파일 in sftp.listdir(folder_서버) if not 파일.startswith('.'))

                # 기준일 적용
                li_로컬파일 = [파일 for 파일 in li_로컬파일 if re.findall(r'\d{8}', 파일)[0] >= s_기준일]\
                            if s_기준일 is not None else li_로컬파일
                li_서버파일 = [파일 for 파일 in li_서버파일 if re.findall(r'\d{8}', 파일)[0] >= s_기준일]\
                            if s_기준일 is not None else li_서버파일

                # 대상파일 확인
                li_대상파일 = [파일 for 파일 in li_로컬파일 if 파일 not in li_서버파일] if s_모드 == '로컬2서버' else\
                            [파일 for 파일 in li_서버파일 if 파일 not in li_로컬파일] if s_모드 == '서버2로컬' else list()

                # 대상폴더 정의
                folder_원본 = folder_로컬 if s_모드 == '로컬2서버' else folder_서버 if s_모드 == '서버2로컬' else None
                folder_타겟 = folder_서버 if s_모드 == '로컬2서버' else folder_로컬 if s_모드 == '서버2로컬' else None

                # 파일 복사
                for s_파일명 in li_대상파일:
                    # 경로 정의
                    path_원본 = f'{folder_원본}/{s_파일명}'
                    path_타겟 = f'{folder_타겟}/{s_파일명}'

                    # 파일 복사
                    ret = sftp.put(path_원본, path_타겟) if s_모드 == '로컬2서버' else\
                            sftp.get(path_원본, path_타겟) if s_모드 == '서버2로컬' else None

                    # 정보 등록
                    li_동기화파일명.append(s_파일명)

        return li_동기화파일명


    def sftp폴더동기화(self, folder_로컬, folder_서버, s_모드, s_시작일자=None):
        """ sftp 서버 접속 후 해당 폴더 동기화 - 하위폴더 포함, 파일 수정시간 기준 """
        # 서버정보 정의
        dic_서버정보 = json.load(open(os.path.join(self.folder_프로젝트, 'server_info.json'), mode='rt', encoding='utf-8'))
        dic_서버접속 = dic_서버정보['sftp']
        dic_서버폴더 = dic_서버정보['folder']

        # 폴더정보 정의
        s_공통폴더_서버 = dic_서버폴더['server_work']
        s_폴더명 = folder_서버.replace(s_공통폴더_서버, '')
        s_공통폴더_로컬 = folder_로컬.replace('\\', '/').replace(s_폴더명, '')

        # 서버 접속
        li_동기화파일명 = list()
        with (paramiko.SSHClient() as ssh):
            # ssh 서버 연결 (알수없는 서버 경고 방지 포함)
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostname=dic_서버접속['hostname'], port=dic_서버접속['port'],
                        username=dic_서버접속['username'], password=dic_서버접속['password'])

            # sftp 세션 시작
            with ssh.open_sftp() as sftp:
                # 하위 폴더 확인 - 서버 기준
                li_대상폴더_서버 = [folder_서버]
                while True:
                    li_하위폴더 = [f'{대상폴더}/{객체.filename}'.replace('\\', '/')
                                    for 대상폴더 in li_대상폴더_서버
                                    for 객체 in sftp.listdir_attr(대상폴더) if 객체.longname[0] == 'd']
                    li_하위폴더 = [폴더 for 폴더 in li_하위폴더 if 폴더 not in li_대상폴더_서버]
                    li_대상폴더_서버 = li_대상폴더_서버 + li_하위폴더
                    if len(li_하위폴더) == 0:
                        break

                # 대상폴더별 파일 동기화
                for s_서버폴더 in sorted(li_대상폴더_서버):
                    # 로컬폴더 정의
                    s_로컬폴더 = s_공통폴더_로컬 + s_서버폴더.replace(s_공통폴더_서버, '')
                    os.makedirs(s_로컬폴더, exist_ok=True)
                    print(f'동기화 진행 - {s_서버폴더}')

                    # 폴더 내 파일 확인
                    li_로컬파일 = sorted(파일 for 파일 in os.listdir(s_로컬폴더)
                                        if not 파일.startswith('.') and os.path.isfile(os.path.join(s_로컬폴더, 파일)))
                    li_서버파일 = sorted(객체.filename for 객체 in sftp.listdir_attr(s_서버폴더)
                                        if not 객체.filename.startswith('.') and 객체.longname[0] == '-')
                    # 시작일자 적용
                    li_로컬파일 = [파일 for 파일 in li_로컬파일 if re.findall(r'\d{8}', 파일)[0] >= s_시작일자]\
                                    if s_시작일자 is not None else li_로컬파일
                    li_서버파일 = [파일 for 파일 in li_서버파일 if re.findall(r'\d{8}', 파일)[0] >= s_시작일자]\
                                    if s_시작일자 is not None else li_서버파일
                    # 대상파일 확인
                    li_대상파일 = li_로컬파일 if s_모드 == '로컬2서버' else li_서버파일 if s_모드 == '서버2로컬' else list()
                    if len(li_대상파일) == 0:
                        continue

                    # 대상폴더 정의
                    folder_원본 = s_로컬폴더 if s_모드 == '로컬2서버' else s_서버폴더 if s_모드 == '서버2로컬' else None
                    folder_타겟 = s_서버폴더 if s_모드 == '로컬2서버' else s_로컬폴더 if s_모드 == '서버2로컬' else None

                    # 파일 복사
                    li_파일_타겟 = li_서버파일 if s_모드 == '로컬2서버' else li_로컬파일 if s_모드 == '서버2로컬' else list()
                    for s_파일명 in li_대상파일:
                        # 경로 정의
                        path_원본 = f'{folder_원본}/{s_파일명}'
                        path_타겟 = f'{folder_타겟}/{s_파일명}'

                        # 파일정보 확인
                        n_수정시간_원본 = int(os.path.getmtime(path_원본)) if s_모드 == '로컬2서버' else\
                                        sftp.stat(path_원본).st_mtime if s_모드 == '서버2로컬' else 0
                        n_수정시간_타겟 = 0 if s_파일명 not in li_파일_타겟 else\
                                        sftp.stat(path_타겟).st_mtime if s_모드 == '로컬2서버' else\
                                        int(os.path.getmtime(path_타겟)) if s_모드 == '서버2로컬' else 0
                        if n_수정시간_원본 <= n_수정시간_타겟:
                            continue

                        # 파일 복사
                        ret = sftp.put(path_원본, path_타겟) if s_모드 == '로컬2서버' else \
                            sftp.get(path_원본, path_타겟) if s_모드 == '서버2로컬' else None

                        # 정보 등록
                        li_동기화파일명.append(s_파일명)

        return li_동기화파일명

    def sftp파일업로드(self, folder_로컬, folder_서버, s_파일명, n_파일보관일수):
        """ sftp 서버 접속 후 해당 파일 업로드 """
        # 서버정보 정의
        dic_서버정보 = json.load(open(os.path.join(self.folder_프로젝트, 'server_info.json'), mode='rt', encoding='utf-8'))
        dic_서버접속 = dic_서버정보['sftp']
        dic_서버폴더 = dic_서버정보['folder']

        # path 정의
        path_로컬 = os.path.join(folder_로컬, s_파일명).replace('\\', '/')
        path_서버 = os.path.join(dic_서버폴더['server_kakao'], folder_서버, s_파일명).replace('\\', '/')

        # 서버 접속
        li_복사한파일명 = list()
        li_삭제한파일명 = list()
        with paramiko.SSHClient() as ssh:
            # ssh 서버 연결 (알수없는 서버 경고 방지 포함)
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostname=dic_서버접속['hostname'], port=dic_서버접속['port'],
                        username=dic_서버접속['username'], password=dic_서버접속['password'])

            # sftp 세션 시작
            with ssh.open_sftp() as sftp:
                # 폴더 생성
                s_서버폴더 = path_서버.replace(s_파일명, '')
                try:
                    sftp_stat = sftp.stat(s_서버폴더)
                except IOError:
                    sftp.mkdir(s_서버폴더)

                # 파일 복사
                ret = sftp.put(path_로컬, path_서버)
                li_복사한파일명.append(s_파일명)

                # 오래된 파일 삭제
                s_파일일자 = re.findall(r'\d{8}', s_파일명)[0]
                s_기준일자 = (pd.Timestamp(s_파일일자) - pd.Timedelta(days=n_파일보관일수)).strftime('%Y%m%d')
                li_삭제파일 = sorted(파일 for 파일 in sftp.listdir(s_서버폴더)
                                 if 파일[0] != '.' and re.findall(r'\d{8}', 파일)[0] < s_기준일자)
                for s_삭제파일 in li_삭제파일:
                    sftp.remove(f'{s_서버폴더}/{s_삭제파일}')
                    li_삭제한파일명.append(s_삭제파일)

        return li_복사한파일명, li_삭제한파일명, dic_서버정보

    @staticmethod
    def find_주문단가(n_기준가, n_틱보정=None, n_수익률보정=None):
        """ 주문가 산정을 위해 해당 종목의 현재가 대비 호가보정 후 int 리턴 """
        ''' ### 호가단위 기준 (23.01.25 기준, 코스피/코스닥 동일)
            2,000원 미만 : 1원
            2,000원 이상 ~ 5,000원 미만 : 5원
            5,000원 이상 ~ 20,000원 미만 : 10원
            20,000원 이상 ~ 50,000원 미만 : 50원
            50,000원 이상 ~ 200,000원 미만 : 100원
            200,000원 이상 ~ 500,000원 미만 : 500원
            500,000원 이상 : 1,000원 '''

        # 호가단위 생성
        li_호가단위 = sorted(
            list(range(0, 2 * 1000, 1))
            + list(range(2 * 1000, 5 * 1000, 5))
            + list(range(5 * 1000, 20 * 1000, 10))
            + list(range(20 * 1000, 50 * 1000, 50))
            + list(range(50 * 1000, 200 * 1000, 100))
            + list(range(200 * 1000, 500 * 1000, 500))
            + list(range(500 * 1000, max(int(n_기준가 * 1.4), 501 * 1000), 1000))
        )
          # + list(range(500 * 1000, 3000 * 1000, 1000)))

        # # 50만원 이상 구간 추가
        # li_호가단위_추가 = list()
        # if n_현재가 >= 500000:
        #     for n_호가 in range(500000, n_현재가 + 10 * 1000, 1000):
        #         li_호가단위_추가.append(n_호가)
        # li_호가단위 = sorted(li_호가단위 + list(range(500000, n_기준가 + 10 * 1000, 1000))) if n_기준가 >= 500000 else li_호가단위

        # 주문단가 산출
        n_주문단가 = None

        # 틱보정 확인
        if n_틱보정 is not None:
            if n_틱보정 > 0:
                li_호가 = [호가 for 호가 in li_호가단위 if 호가 > n_기준가]
                n_주문단가 = li_호가[n_틱보정 - 1]

            elif n_틱보정 < 0:
                li_호가 = [호가 for 호가 in li_호가단위 if 호가 < n_기준가]
                n_주문단가 = li_호가[n_틱보정]

            else:
                n_주문단가 = n_기준가

        # 수익률보정 확인
        if n_수익률보정 is not None:
            n_수익률단가 = n_기준가 * (1 + n_수익률보정 / 100)
            n_주문단가 = min(호가 for 호가 in li_호가단위 if 호가 >= n_수익률단가)

        return n_주문단가

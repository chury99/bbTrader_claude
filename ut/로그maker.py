import os
import sys
import json
import pandas as pd

import ut.도구manager


# noinspection NonAsciiCharacters,PyPep8Naming,SpellCheckingInspection
class LogMaker:
    def __init__(self, s_파일명, s_로그명):
        # config 읽어 오기
        self.folder_베이스 = os.path.dirname(os.path.abspath(__file__))
        self.folder_프로젝트 = os.path.dirname(self.folder_베이스)
        self.s_파일명 = os.path.basename(__file__).replace('.py', '')
        # dic_config = json.load(open(os.path.join(self.folder_프로젝트, 'config.json'), mode='rt', encoding='utf-8'))
        dic_config = ut.도구manager.config로딩()

        # 기준정보 정의
        self.s_오늘 = pd.Timestamp.now().strftime('%Y%m%d')
        self.s_파일명_상위 = s_파일명
        self.path_로그 = os.path.join(dic_config['folder_log'], f'{dic_config[s_로그명]}_{self.s_오늘}.log')
        self.path_에러 = os.path.join(dic_config['folder_log'], f'{dic_config['로그이름_error']}_{self.s_오늘}.log')


    def make_로그(self, s_내용, li_출력=None):
        """ 입력 받은 s_내용에 시간 및 구분자 붙여서 저장 """
        # 정보 설정
        s_시각 = pd.Timestamp.now().strftime('%H:%M:%S')
        s_모듈 = sys._getframe(1).f_code.co_name

        # 로그 생성
        s_로그 = f'[{s_시각}] {self.s_파일명_상위} | {s_모듈} | {s_내용}'

        # log 출력
        li_출력 = ['콘솔', '파일'] if li_출력 is None else li_출력
        if '콘솔' in li_출력:
            print(s_로그)
        if '파일' in li_출력:
            with open(self.path_로그, mode='at', encoding='utf-8') as f:
                f.write(f'{s_로그}\n')


# noinspection PyMethodMayBeStatic,PyPep8Naming,NonAsciiCharacters,PyUnusedLocal,SpellCheckingInspection
class StderrHook:
    def __init__(self, path_에러로그):
        # 기준정보 지정
        self.stderr_콘솔 = sys.__stderr__
        self.path_에러로그 = path_에러로그

    def write(self, s_error):
        """ stderr 앞에 메세지 추가 및 저장 """# 에러 발생 시 메세지 추가
        if 'Traceback' in s_error:
            s_현재 = pd.Timestamp.now().strftime('%Y%m%d %H:%M:%S')
            s_추가메세지 = f'\n---------- {s_현재} ----------\n'
            self.stderr_콘솔.write(s_추가메세지)
            with open(self.path_에러로그, mode='at', encoding='utf-8') as f:
                f.write(s_추가메세지)

        # 원래 에러 메세지 추가
        self.stderr_콘솔.write(s_error)
        with open(self.path_에러로그, mode='at', encoding='utf-8') as f:
            f.write(s_error)

    def flush(self):
        """ 버퍼 비원주는 함수 """
        self.stderr_콘솔.flush()

if __name__ == '__main__':
    pass

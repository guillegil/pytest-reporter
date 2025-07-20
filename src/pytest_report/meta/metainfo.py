from pytest import Item, CallInfo

import pytest

class MetaInfo:
    def __init__(self):
        self.__current_testcase  : str  = ""
        self.__current_filename  : str  = ""
        self.__current_testproto : str  = ""

        self.__current_testinfo = {}

        self.__run_info : list = {
            "total_passed": 0,
            "total_failed": 0,
            "total_skipped": 0,

            "testinfo": {},
        }

        # TODO: Meta info to be described for the run
        # a = {
        #   "total_passed": 0,
        #   "total_failed": 0,
        #   "total_skipped": 0,
      
        #   "test_file.py": {
        #         "is_test_file": True,
        #         "test_almsa": [
        #             {
        #                 "index": 0,

        #                 "setup": {
        #                     "start": 0,
        #                     "finished": 10,
        #                     "execution_time": 10,

        #                     "log": "",
        #                     "status": "",
        #                 },

        #                 "call": {
        #                     "inputs": {
        #                         "a": 1,
        #                         "b": 5.3
        #                     },

        #                     "status": "passed"
        #                 }
        #             }   
        #         ],
        #   },

        #   "parent": "MMDC"  
        # }

        # TODO: Not implemented yet
        self.__next_testcase  : str = ""
        self.__next_filename  : str = ""
        self.__next_testproto : str = ""

        self.__current_item : Item | None = None
        self.__next_item    : Item | None = None
    
    @property
    def current_testcase(self) -> str:
        return self.__current_testcase
    
    @current_testcase.setter
    def current_testcase(self, testcase: str) -> None:
        self.__current_testcase = testcase

    @property
    def current_filename(self) -> str:
        return self.__current_filename
    
    @current_filename.setter
    def current_filename(self, filename: str) -> None:
        self.__current_filename = filename

    @property
    def current_testproto(self) -> str:
        return self.__current_testproto
    
    @current_testproto.setter
    def current_testproto(self, testproto: str) -> None:
        self.__current_testproto = testproto

    @property
    def current_test_info(self) -> dict:
        return self.__current_testinfo

    @property
    def run_info(self):
        return self.__run_info

    def append_logline(self, logmsg: str):
        logmsg = logmsg + '\n' if not logmsg.endswith('\n') else logmsg

        if self.current_testproto == "setup" or self.current_testproto == "fake_setup":
            if "setup" not in self.__current_testinfo:
                self.__current_testinfo["setup"] = {}
            
            if "log" not in self.__current_testinfo["setup"]:
                self.__current_testinfo["setup"]["log"] = ""

            self.__current_testinfo["setup"]["log"] += logmsg

        elif self.current_testproto == "call":
            if "call" not in self.__current_testinfo:
                self.__current_testinfo["call"] = {}
            
            if "log" not in self.__current_testinfo["call"]:
                self.__current_testinfo["call"]["log"] = ""

            self.__current_testinfo["call"]["log"] += logmsg

        elif self.current_testproto == "teardown":
            if "teardown`" not in self.__current_testinfo:
                self.__current_testinfo["teardown"] = {}
            
            if "log" not in self.__current_testinfo["teardown"]:
                self.__current_testinfo["teardown"]["log"] = ""

            self.__current_testinfo["teardown"]["log"] += logmsg
        else:
            pass

    def append_item(self, item: Item, call_info: CallInfo):
        from pprint import pprint

        if self.current_filename not in self.__run_info["testinfo"]:
            self.__run_info["testinfo"][self.current_filename] = {}
        elif self.current_testcase not in self.__run_info["testinfo"][self.current_filename]:
            self.__run_info["testinfo"][self.current_filename][self.current_testcase] = []
        else:
            pass

        if call_info.when == "setup":
            if "setup" not in self.__current_testinfo:
                self.__current_testinfo["setup"] = {}

            self.__current_testinfo["setup"]["start"] = call_info.start
            self.__current_testinfo["setup"]["stop"] = call_info.stop
            self.__current_testinfo["setup"]["duration"] = call_info.duration

            if call_info.excinfo is None:
                self.__current_testinfo["setup"]["status"] = "passed"
            elif issubclass(call_info.excinfo.type, pytest.skip.Exception):
                self.__current_testinfo["setup"]["status"] = "skipped"
            elif issubclass(call_info.excinfo.type, pytest.fail.Exception) or issubclass(call_info.excinfo.type, AssertionError):
                self.__current_testinfo["setup"]["status"] = "failed"
            else:
                self.__current_testinfo["setup"]["status"] = "error"
                

        if call_info.when == "call":
            if "call" not in self.__current_testinfo:
                self.__current_testinfo["call"] = {}

            self.__current_testinfo["call"]["start"] = call_info.start
            self.__current_testinfo["call"]["stop"] = call_info.stop
            self.__current_testinfo["call"]["duration"] = call_info.duration

            if call_info.excinfo is None:
                self.__current_testinfo["call"]["status"] = "passed"
            elif issubclass(call_info.excinfo.type, pytest.skip.Exception):
                self.__current_testinfo["call"]["status"] = "skipped"
            elif issubclass(call_info.excinfo.type, pytest.fail.Exception) or issubclass(call_info.excinfo.type, AssertionError):
                self.__current_testinfo["call"]["status"] = "failed"
            else:
                self.__current_testinfo["call"]["status"] = "error"
                

        if call_info.when == "teardown":
            self.__run_info["testinfo"][self.current_filename][self.current_testcase].append(self.__current_testinfo)
            self.__current_testinfo = {}
                
meta = MetaInfo()

if __name__ == "__main__":
    pass
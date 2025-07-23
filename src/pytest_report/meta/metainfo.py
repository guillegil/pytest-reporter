from pytest import Item, CallInfo, TestReport, Config

import pytest

import os
import json

class MetaInfo:
    def __init__(self):
        self.__current_testcase   : str  = ""
        self.__current_filename   : str  = ""
        self.__current_testpath   : str  = ""
        self.__current_testproto  : str  = ""
        self.__current_testargs   : dict = {}
        self.__current_test_index : int = 0

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
    def current_testpath(self) -> str:
        return self.__current_testpath
    
    @current_testpath.setter
    def current_testpath(self, testpath: str) -> None:
        self.__current_testpath = testpath

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
    def current_testargs(self) -> str:
        return self.__current_testargs
    
    @current_testargs.setter
    def current_testargs(self, testargs: str) -> None:
        self.__current_testargs = testargs

    @property
    def current_test_index(self) -> int:
        return self.__current_test_index
    
    @current_test_index.setter
    def current_test_index(self, index: int) -> None:
        self.__current_test_index = index


    @property
    def run_info(self) -> dict:
        return self.__run_info
    
    @property
    def testinfo(self) -> dict:
        return self.__run_info["testinfo"]

    @property
    def current_testinfo(self) -> dict:
        return self.testinfo[self.current_filename][self.current_testcase][self.current_test_index]

    @property
    def current_testlog(self) -> str:
        proto = self.current_testproto
        if self.current_testproto == "fake_setup":
            proto = "setup"

        return self.testinfo[self.current_filename][self.current_testcase][self.current_test_index][proto]["log"]

    @current_testlog.setter
    def current_testlog(self, log: str) -> None:
        proto = self.current_testproto
        if self.current_testproto == "fake_setup":
            proto = "setup"

        self.testinfo[self.current_filename][self.current_testcase][self.current_test_index][proto]["log"] += log

    @property
    def current_setup_status(self) -> str:
        return self.current_testinfo["setup"]["status"]

    @property
    def current_call_status(self) -> str:
        return self.current_testinfo["call"]["status"]


    def _update_run_info(self):
        if self.current_testproto == "setup":
            if self.current_filename not in self.testinfo:
                self.testinfo[self.current_filename] = {}
            
            if self.current_testcase not in self.testinfo[self.current_filename]:
                self.testinfo[self.current_filename][self.current_testcase] = []
                self.current_test_index = 0
            else:
                self.current_test_index += 1

            self.testinfo[self.current_filename][self.current_testcase].append({
                "index": self.current_test_index,
                "setup": {
                    "log": "",
                    "status": "",
                },
                "call": {
                    "inputs": self.current_testargs,
                    "log": "",
                    "status": "",
                },
                "teardown": {},
            })
        elif self.current_testproto == "call":
            pass
        elif self.current_testproto == "teardown":
            pass
        else:
            pass

    def update_item_setup(self, item: Item):
        self.current_testproto = "setup"

        self.current_testcase  = item.originalname
        self.current_testpath  = item.fspath.dirname
        self.current_filename  = item.fspath.basename

        if hasattr(item, "callspec"):
            self.current_testargs = item.callspec.params

        self._update_run_info()

    def update_item_call(self, item: Item):
        meta.current_testcase  = item.originalname
        meta.current_testpath  = item.fspath.dirname
        meta.current_filename  = item.fspath.basename
        meta.current_testproto = "call"

    def update_item_teardown(self, item: Item):
        meta.current_testcase  = item.originalname
        meta.current_testpath  = item.fspath.dirname
        meta.current_filename  = item.fspath.basename
        meta.current_testproto = "teardown"

        self._update_run_info()

    def update_test_status(self, item: Item, call: CallInfo):
        if call.when == "call":
            if call.excinfo is None:
                self.current_testinfo["call"]["status"] = "passed"
            elif issubclass(call.excinfo.type, pytest.skip.Exception):
                self.current_testinfo["call"]["status"] = "skipped"
            elif issubclass(call.excinfo.type, AssertionError):
                self.current_testinfo["call"]["status"] = "failed"
            else:
                self.current_testinfo["call"]["status"] = "error"
            

            self.current_testinfo["call"]["start"] = call.start
            self.current_testinfo["call"]["stop"] = call.stop
            self.current_testinfo["call"]["duration"] = call.duration

        elif call.when == "setup":
            if call.excinfo is None:
                self.current_testinfo["setup"]["status"] = "passed"
            elif issubclass(call.excinfo.type, pytest.skip.Exception):
                self.current_testinfo["setup"]["status"] = "skipped"
            elif issubclass(call.excinfo.type, AssertionError):
                self.current_testinfo["setup"]["status"] = "failed"
            else:
                self.current_testinfo["setup"]["status"] = "error"

            self.current_testinfo["setup"]["start"] = call.start
            self.current_testinfo["setup"]["stop"] = call.stop
            self.current_testinfo["setup"]["duration"] = call.duration
        else:
            pass

    def export_json(self, path: str = "./") -> None:
        if not path.endswith(".json"):
            if os.path.isdir(path):
                path = os.path.join(path, "run_info.json")
            else:
                path += ".json"

        with open(path, "w") as json_file:
            json.dump(self.run_info, json_file, indent=4)


meta = MetaInfo()

if __name__ == "__main__":
    pass
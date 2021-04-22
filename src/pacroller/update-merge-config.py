#!/usr/bin/python

from pacroller.config import CONFIG_DIR, CONFIG_FILE
import json

def main() -> None:
    oldcfg = CONFIG_DIR / CONFIG_FILE
    newcfg = CONFIG_DIR / f"{CONFIG_FILE}.pacnew"
    assert oldcfg.exists()
    assert newcfg.exists()
    old: dict = json.loads(oldcfg.read_text())
    new: dict = json.loads(newcfg.read_text())
    new_copy = new.copy()
    for k, v in new.items():
        if isinstance(v, (int, str, bool)):
            if old.get(k, None) is None:
                print(f"use default value {k} = {v} for new option {k}")
            else:
                if old[k] != v:
                    print(f"use custom value {k} = {old[k]} while default value is {v}")
                    new_copy[k] = old[k]
        elif isinstance(v, list):
            if k == "need_restart_cmd":
                if old[k] != v:
                    print(f"use custom value {k} = {old[k]} while default value is {v}")
                    new_copy[k] = old[k]
            else:
                _new = list()
                for _item in [*old[k], *v]:
                    if _item not in _new:
                        _new.append(_item)
                if _new != old[k]:
                    print(f"merged {old[k]} and {v} to {_new}")
                    new_copy[k] = _new
        elif isinstance(v, dict):
            for _o in old.get(k, {}):
                if v.get(_o) != old[k][_o]:
                    print(f"use custom value {k}[{_o}] = {old[k][_o]} while default value is {v.get(_o)}")
                    new_copy[k][_o] = old[k][_o]
            for _o in v:
                if _o not in old.get(k, {}):
                    print(f"new value {k}[{_o}] = {v[_o]}")

    oldcfg.rename(CONFIG_DIR / f"{CONFIG_FILE}.pacsave")
    oldcfg.write_text(json.dumps(new_copy, indent=4)+"\n")
    print("wrote new config")

if __name__ == '__main__':
    main()

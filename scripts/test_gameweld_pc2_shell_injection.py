#!/usr/bin/env python3
"""Compile the actual GTK C argv helper and test attacker-controlled metadata."""
from __future__ import annotations
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

C_SOURCE = (Path(__file__).resolve().parents[1] /
            "crates/wand-ui/appimage-gtk3/gameweld-native-040.c")


class NoShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = C_SOURCE.read_text()
        begin = cls.source.index("/* Shell-free helper:")
        end = cls.source.index("static void state_safe_id(", begin)
        cls.helper = cls.source[begin:end]

    def test_no_shell_dispatch_in_gtk_source(self):
        for pattern in (r"\bpopen\s*\(", r"\bsystem\s*\(", r"\bpclose\s*\("):
            self.assertNotRegex(self.source, pattern)
        self.assertEqual(self.source.count("g_mkdir_with_parents(dir,0700)"), 6)

    def test_game_metadata_and_cheat_engine_are_exact_argv(self):
        for name in ("steam_shortcuts_tool()", "heroic_provider_tool()",
                     "lutris_provider_tool()"):
            self.assertIn('pc2_read_argv("python3",' + name +
                          ',"list",NULL,&read_pid)', self.source)
        for mode in ("detect", "windows-detect"):
            self.assertIn('pc2_read_argv(cheat_engine_manager(),"' + mode +
                          '",appid,NULL,&read_pid)', self.source)

    def test_adversarial_metadata_cannot_execute_through_real_c_helper(self):
        compiler = shutil.which("gcc") or shutil.which("cc")
        if not compiler:
            self.skipTest("C compiler unavailable")
        with tempfile.TemporaryDirectory(prefix="gw-shell-audit-") as directory:
            root = Path(directory)
            exe = root / "helper's tool"
            marker = root / "not-created"
            exe.write_text('#!/bin/sh\nprintf "%s\\n" "$2"\n')
            exe.chmod(0o700)
            src = root / "test.c"
            binpath = root / "test"
            src.write_text(
                '#define _GNU_SOURCE\n#include <stdio.h>\n#include <stdlib.h>\n'
                '#include <unistd.h>\n#include <errno.h>\n#include <fcntl.h>\n'
                '#include <sys/wait.h>\n'
                + self.helper +
                '\nint main(int argc,char **argv){\n'
                '  if(argc!=3)return 5;\n'
                '  pid_t child=-1;\n'
                '  FILE *f=pc2_read_argv(argv[1],"detect",argv[2],NULL,&child);\n'
                '  if(!f)return 6;\n'
                '  char buf[4096];if(!fgets(buf,sizeof buf,f))return 7;\n'
                '  fputs(buf,stdout);\n'
                '  return pc2_close_read_argv(f,child)?0:8;\n}\n')
            subprocess.run([compiler,"-Wall","-Wextra","-Werror","-std=c11",
                            str(src),"-o",str(binpath)],
                           capture_output=True,text=True,check=True)
            attacks = [
                '123; touch "' + str(marker) + '"',
                'heroic-$(touch "' + str(marker) + '")',
                "lutris-'; touch " + str(marker) + "; #",
                "steam-" + chr(96) + "touch " + str(marker) + chr(96),
            ]
            for payload in attacks:
                with self.subTest(payload=payload):
                    result = subprocess.run([str(binpath),str(exe),payload],
                                            capture_output=True,text=True,
                                            check=True,timeout=4)
                    self.assertEqual(result.stdout,payload+"\n")
                    self.assertFalse(marker.exists())

if __name__ == "__main__":
    unittest.main()

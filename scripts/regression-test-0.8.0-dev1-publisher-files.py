#!/usr/bin/env python3
"""GameWeld 0.8.0 dev1: first-party browser download evidence, no installs."""
import importlib.util, io, json, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).with_name('gameweld-trainer-updates.py')
spec=importlib.util.spec_from_file_location('gw_08_files',P)
u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
PAGE='https://flingtrainer.com/trainer/control-resonant-trainer/'
FILENAME='CONTROL.Resonant.v1.0-v1.4.x.Plus.26.Trainer-FLiNG'
HTML=f'''<html><h1>CONTROL Resonant Trainer</h1><table><tr><th>Download</th><th>File</th><th>Date added</th><th>Size</th></tr>
<tr><td><a href="https://evil.example/bad.exe">advertisement</a></td><td><a href="/downloads/3gpf4mkYk1fCoZ1UTmD08Q%2C%2C">{FILENAME}</a></td><td>2026-10-06 12:20</td><td>946 KB</td></tr>
<tr><td><a href="/downloads/badfile00000">unrelated</a></td><td>Assassins.Creed.Mirage.v1.0.4.Plus.19.Trainer-FLiNG</td><td>2026-10-07</td></tr>
</table></html>'''
class OfficialFiles(unittest.TestCase):
    def test_exact_official_row(self):
        r=u.official_page_links('CONTROL Resonant',PAGE,HTML)
        self.assertEqual(r['count'],1)
        self.assertEqual(r['releases'][0]['name'],FILENAME)
        self.assertEqual(r['releases'][0]['published'],'2026-10-06')
        self.assertIn('flingtrainer.com/downloads/',r['releases'][0]['official_link'])
        self.assertFalse(r['authenticated']);self.assertFalse(r['downloaded'])
    def test_no_cross_game_links(self):
        r=u.official_page_links('CONTROL Resonant',PAGE,HTML.replace(FILENAME,'Assassins.Creed.Mirage.v1.0.4.Plus.19.Trainer-FLiNG'))
        self.assertEqual(r['count'],0)
    def test_no_wrong_page_game(self):
        with self.assertRaisesRegex(u.UpdateError,'does not match'):u.official_page_links('CONTROL',PAGE,HTML)
    def test_no_external_or_unsafe_download_url(self):
        for href in ('https://evil.example/downloads/123456789','https://flingtrainer.com.evil.example/downloads/123456789',
                     'http://flingtrainer.com/downloads/123456789','/downloads/%2e%2e%2fsecret','/downloads/123456789?x=1',
                     'https://flingtrainer.com@evil.example/downloads/123456789'):
            with self.subTest(href=href):
                trial=HTML.replace('/downloads/3gpf4mkYk1fCoZ1UTmD08Q%2C%2C',href)
                self.assertEqual(u.official_page_links('CONTROL Resonant',PAGE,trial)['count'],0)
    def test_no_wrong_anchor_cell(self):
        changed=HTML.replace(f'>{FILENAME}</a>', '>Not the package name</a>')
        self.assertEqual(u.official_page_links('CONTROL Resonant',PAGE,changed)['count'],0)
    def test_ambiguous_links_rejected(self):
        changed=HTML.replace(f'>{FILENAME}</a>',f'>{FILENAME}</a><a href="/downloads/otherlink1234567">{FILENAME}</a>')
        self.assertEqual(u.official_page_links('CONTROL Resonant',PAGE,changed)['count'],0)
    def test_filename_metadata_parser_preserved(self):
        meta=u.publisher_page_metadata('fling',HTML)
        self.assertEqual(meta['publisher_releases'][0]['name'],FILENAME)
    def test_cli_fixture_no_network(self):
        with tempfile.TemporaryDirectory() as d:
            fixture=Path(d)/'page.html';fixture.write_text(HTML)
            p=subprocess.run([sys.executable,str(P),'publisher-files','--game','CONTROL Resonant','--page',PAGE,'--html-file',str(fixture),'--plain'],text=True,capture_output=True,timeout=8)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            self.assertIn('FILE\t'+FILENAME,p.stdout)
            self.assertIn('NO PUBLISHER-AUTHENTICATED CHECKSUM',p.stdout.upper())
    def test_package_links_not_catalog_downloads(self):
        r=u.official_page_links('CONTROL Resonant',PAGE,HTML)
        rec=r['releases'][0]
        with self.assertRaises(u.UpdateError):
            u.validate_catalog({'schema':1,'entries':[{'id':'x','game':'CONTROL Resonant','version':'1.0','provider':'fling','url':rec['official_link'],'sha256':'0'*64}]})
    def test_no_network_in_fixture_mode(self):
        with patch.object(u,'open_trusted',side_effect=AssertionError('unexpected fetch')):
            self.assertEqual(u.official_page_links('CONTROL Resonant',PAGE,HTML)['count'],1)
if __name__=='__main__':unittest.main(verbosity=2)

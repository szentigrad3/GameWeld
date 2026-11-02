import json
import os
import tempfile
import unittest
from pathlib import Path
from gameweld import core
from gameweld.diagnostics import game_report


def manifest(appid=100, title='Example Game', installdir='Example Game', buildid='123'):
    return (f'"AppState" {{\n"appid" "{appid}"\n"name" "{title}"\n'
            f'"installdir" "{installdir}"\n"buildid" "{buildid}"\n}}\n')

class VDFTests(unittest.TestCase):
    def test_basic_nested(self):
        parsed=core.parse_vdf('"one" {"two" "three" "four" {"five" "six"}}')
        self.assertEqual(parsed['one']['four']['five'],'six')

    def test_comments(self):
        self.assertEqual(core.parse_vdf('// test\n"x" "y" // trailing\n')['x'],'y')

    def test_unquoted_number_key(self):
        self.assertEqual(core.parse_vdf('"libraryfolders" { 1 { "path" "/tmp/a" } }')['libraryfolders']['1']['path'],'/tmp/a')

    def test_escaped_quote(self):
        self.assertEqual(core.parse_vdf('"x" "quoted \\"word\\""')['x'],'quoted "word"')

    def test_reject_broken(self):
        for sample in ('"x" {','"x" }','{', '"x" "ok" }', '"x"'):
            with self.subTest(sample=sample),self.assertRaises(ValueError):
                core.parse_vdf(sample)

    def test_too_deep(self):
        with self.assertRaises(ValueError):
            core.parse_vdf('"a" {'*30+'}'*30)

class SteamTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name)/'steamapps'
        self.root.mkdir()

    def save(self,appid=100,title='Example Game',**kw):
        (self.root/f'appmanifest_{appid}.acf').write_text(manifest(appid,title,**kw))

    def test_one(self):
        self.save()
        games=core.installed_games(self.root)
        self.assertEqual(len(games),1)
        self.assertEqual(games[0]['buildid'],'123')
        self.assertEqual(games[0]['library'],'primary')

    def test_secondary_library(self):
        alternate=Path(self.t.name)/'secondary'
        (alternate/'steamapps').mkdir(parents=True)
        (alternate/'steamapps'/'appmanifest_200.acf').write_text(manifest(200,'Second'))
        (self.root/'libraryfolders.vdf').write_text(
            f'"libraryfolders" {{\n"0" {{"path" "{self.root.parent}"}}\n'
            f'"1" {{"path" "{alternate}"}}\n}}')
        self.save()
        games=core.installed_games(self.root)
        self.assertEqual([g['appid'] for g in games],[100,200])
        self.assertEqual(games[1]['library'],'secondary')

    def test_reject_mismatched_appid(self):
        (self.root/'appmanifest_300.acf').write_text(manifest(301))
        self.assertEqual(core.installed_games(self.root),[])

    def test_reject_symlink_manifest(self):
        outside=Path(self.t.name)/'outside'
        outside.write_text(manifest())
        (self.root/'appmanifest_100.acf').symlink_to(outside)
        self.assertEqual(core.installed_games(self.root),[])

    def test_reject_traversal_installdir(self):
        self.save(installdir='../outside')
        game=core.installed_games(self.root)[0]
        self.assertIsNone(game['installdir'])
        self.assertFalse(game_report(game)['install_directory_found'])

    def test_diagnostics_pure_metadata(self):
        self.save()
        game=core.installed_games(self.root)[0]
        (self.root/'common'/'Example Game').mkdir(parents=True)
        (self.root/'compatdata'/'100').mkdir(parents=True)
        report=game_report(game)
        self.assertTrue(report['install_directory_found'])
        self.assertTrue(report['compatdata_directory_found'])
        self.assertFalse(report['game_process_verified'])
        self.assertFalse(report['safe_to_attach'])
        self.assertNotIn(str(self.root), json.dumps(report))

    def test_diagnostic_symlink_does_not_count(self):
        self.save()
        (self.root/'common').mkdir()
        (self.root/'common'/'Example Game').symlink_to(self.root)
        self.assertFalse(game_report(core.installed_games(self.root)[0])['install_directory_found'])

    def test_empty(self):
        self.assertEqual(core.installed_games(self.root),[])

class PreferencesTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as root:
            dest=Path(root)/'config'/'prefs.json'
            core.save_settings({'favourites':[1,2,2], 'notes':{'100':' important '},
                                'steamapps':'/games/steamapps','sort':'favourites'},dest)
            self.assertEqual(dest.stat().st_mode & 0o777,0o600)
            data=core.load_settings(dest)
            self.assertEqual(data['notes']['100'],'important')
            self.assertEqual(data['favourites'],[1,2])
            self.assertEqual(data['sort'],'favourites')

    def test_symlink_blocked(self):
        with tempfile.TemporaryDirectory() as root:
            target=Path(root)/'target'
            target.write_text('{}')
            link=Path(root)/'link'
            link.symlink_to(target)
            self.assertEqual(core.load_settings(link)['favourites'],[])
            with self.assertRaises(ValueError):core.save_settings({},link)

    def test_ignore_bad_notes(self):
        data=core.valid_settings({'notes':{'hi':'hello','23':'x'*1201,'55':'ok'},'sort':'invalid',
                                  'favourites':[True,9,9,0]})
        self.assertEqual(data['notes'],{'55':'ok'})
        self.assertEqual(data['sort'],'title')
        self.assertEqual(data['favourites'],[9])

    def test_filters(self):
        games=[{'appid':20,'title':'Echo'},{'appid':9,'title':'Alpha'}]
        self.assertEqual([g['appid'] for g in core.find_games(games,sort='appid')],[9,20])
        self.assertEqual([g['appid'] for g in core.find_games(games,favourites=[20],sort='favourites')],[20,9])
        self.assertEqual([g['appid'] for g in core.find_games(games,'alp')],[9])
        self.assertEqual([g['appid'] for g in core.find_games(games,'',favourites=[20],only_favourites=True)],[20])

if __name__=='__main__':unittest.main()

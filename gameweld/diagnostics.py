"""Read-only, privacy-aware Steam installation diagnostics."""
import stat
from pathlib import Path


def _real_directory(path):
    try:
        meta = path.lstat()
        return stat.S_ISDIR(meta.st_mode)
    except OSError:
        return False


def game_report(game):
    if not isinstance(game, dict) or type(game.get('appid')) is not int:
        raise ValueError('invalid_game')
    root = Path(game['_steamapps'])
    appid = game['appid']
    common = root / 'common'
    install = game.get('installdir')
    # No user path values are included in the exported JSON.
    installed_directory = bool(install and '/' not in install and '\\' not in install
                               and install not in ('.', '..')
                               and _real_directory(common / install))
    compatdata_dir = _real_directory(root / 'compatdata' / str(appid))
    return {'operation': 'gameweld-readonly-game-report', 'schema_version': 1,
            'appid': appid, 'title': game['title'], 'buildid': game.get('buildid'),
            'steam_manifest_found': True, 'steam_library': game.get('library', 'unknown'),
            'install_directory_found': installed_directory,
            'compatdata_directory_found': compatdata_dir,
            'proton_running_verified': False, 'game_process_verified': False,
            'trainer_compatible': False, 'safe_to_attach': False,
            'game_memory_accessed': False, 'steam_modified': False,
            'raw_paths_disclosed': False, 'trainer_launched': False}

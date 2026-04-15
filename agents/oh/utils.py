import os, time


def find_recent_modified_files(root, minutes=5):
    cutoff = time.time() - minutes * 60

    def scan(dirpath):
        with os.scandir(dirpath) as it:
            for entry in it:
                try:
                    if entry.is_file():
                        if entry.stat().st_mtime >= cutoff:
                            yield os.path.relpath(entry.path, root)
                    elif entry.is_dir():
                        yield from scan(entry.path)
                except (PermissionError, FileNotFoundError):
                    pass

    return list(scan(root))

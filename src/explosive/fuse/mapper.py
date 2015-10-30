from os.path import basename
from logging import getLogger
from zipfile import ZipFile
try:
    from zipfile import BadZipFile
except ImportError:  # pragma: no cover
    # Assume python 2
    from zipfile import BadZipfile as BadZipFile
    FileNotFoundError = IOError  # This is raised by zipfile.

from . import pathmaker

logger = getLogger(__name__)


class DefaultMapper(object):
    """
    Mapper that tracks the nested structure within archive files.
    """

    def __init__(self, path=None, pathmaker_name='default', overwrite=False,
            include_arcname=False):
        """
        Initialize the mapping, optionally with a path to an archive
        file.

        Mapping dict keys are names of file or directory, values are
        either a tuple that represent a file, or a dict to represent a
        directory.
        """

        self.include_arcname = include_arcname
        self.overwrite = overwrite
        self.pathmaker = getattr(pathmaker, pathmaker_name)()
        self.mapping = {}
        if path:
            self.load_archive(path)

    def mkdir(self, path_fragments):
        """
        Creates the dir entries identified by path if not already exists
        and return the complete directory.
        """

        # set current to root node
        current = self.mapping

        for c, frag in enumerate(path_fragments):
            if frag in current:
                current = current[frag]
                if not isinstance(current, dict):
                    raise ValueError(
                        'cannot create directory `%(filename)s` at '
                        '`%(path)s/`: file entry exists.' % {
                            'filename': frag,
                            'path': '/'.join(path_fragments[:c]),
                        }
                    )
            else:
                # create directory dict entry and set current.
                current[frag] = current = {}

        return current

    def traverse(self, path):
        """
        Traverse to path, or return the entry identified by path.
        """

        path_fragments = path and path.split('/') or []
        current = self.mapping

        for frag in path_fragments:
            if not isinstance(current, dict) or frag not in current:
                # No such frag in dir.
                return None
            current = current[frag]

        return current

    def _load_infolist(self, archive_path, infolist):
        archive_name = basename(archive_path) + '/'

        for info in infolist:
            if self.include_arcname:
                ifilename = archive_name + info.filename
            else:
                ifilename = info.filename
            frags, filename = self.pathmaker(ifilename)
            try:
                target = self.mkdir(frags)
            except ValueError as e:
                # using info.filename rather than ifilename because
                # the message is provided by the exception generated by
                # self.mkdir.
                logger.warning(
                    '`%s` could not be created: %s', info.filename, e.args[0])
                continue

            if not filename:
                # was a directory entry
                continue

            if filename in target:
                if not self.overwrite:
                    logger.info('`%s` already exists; ignoring', info.filename)
                    continue
            target[filename] = (archive_path, info.filename, info.file_size)

    def load_archive(self, archive_path):
        """
        Load an archive file identified by archive_path into the
        mapping.
        """

        try:
            with ZipFile(archive_path) as zf:
                self._load_infolist(archive_path, zf.infolist())
            logger.info('loaded `%s`', archive_path)
            return True
        except BadZipFile:
            logger.warning(
                '`%s` appears to be an invalid archive file', archive_path)
        except FileNotFoundError:
            logger.warning(
                '`%s` does not exist.', archive_path)
        except:
            logger.exception('Exception')
        return False

    def readfile(self, path):
        """
        Return the complete file with information contained in path.
        """

        # TODO: alternative implementation return zipinfo.open handler

        info = self.traverse(path)

        archive_filename, filename, _ = info
        with ZipFile(archive_filename) as zf:
            with zf.open(filename) as f:
                return f.read()

    def readdir(self, path):
        """
        Return a listing of all files in a directory
        """

        info = self.traverse(path)
        if not isinstance(info, dict):
            return []
        return list(info.keys())

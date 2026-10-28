"""lstat with the birth time, through glibc's statx (Linux 4.11+, glibc 2.28+).

Python 3.14's os.stat has no st_birthtime on Linux (os.statx arrives in 3.15),
though ext4, xfs and btrfs keep one. One statx call costs what one lstat does
(measured 2026-10-26: ~90 us each over 53k paths, within noise), so it replaces
lstat in the walk rather than adding a second call. Falls back to os.lstat where
statx is unavailable; st_birthtime is then absent, as before.
"""

from __future__ import annotations

import ctypes
import errno
import os
import sys

_AT_FDCWD = -100
_AT_SYMLINK_NOFOLLOW = 0x100
_STATX_BASIC_STATS = 0x07FF
_STATX_BTIME = 0x0800
_STATX_MNT_ID = 0x1000
_STATX_DIOALIGN = 0x2000
_STATX_SUBVOL = 0x8000
# Ask for everything this structure can hold; the kernel fills what it supports and
# says which in stx_mask (kept, so a consumer knows which values are real).
_STATX_REQUEST = _STATX_BASIC_STATS | _STATX_BTIME | _STATX_MNT_ID | _STATX_DIOALIGN | _STATX_SUBVOL


class _Timestamp(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_int64), ("tv_nsec", ctypes.c_uint32), ("_reserved", ctypes.c_int32)]


class _Statx(ctypes.Structure):
    _fields_ = [
        ("stx_mask", ctypes.c_uint32), ("stx_blksize", ctypes.c_uint32),
        ("stx_attributes", ctypes.c_uint64), ("stx_nlink", ctypes.c_uint32),
        ("stx_uid", ctypes.c_uint32), ("stx_gid", ctypes.c_uint32),
        ("stx_mode", ctypes.c_uint16), ("_spare0", ctypes.c_uint16),
        ("stx_ino", ctypes.c_uint64), ("stx_size", ctypes.c_uint64),
        ("stx_blocks", ctypes.c_uint64), ("stx_attributes_mask", ctypes.c_uint64),
        ("stx_atime", _Timestamp), ("stx_btime", _Timestamp),
        ("stx_ctime", _Timestamp), ("stx_mtime", _Timestamp),
        ("stx_rdev_major", ctypes.c_uint32), ("stx_rdev_minor", ctypes.c_uint32),
        ("stx_dev_major", ctypes.c_uint32), ("stx_dev_minor", ctypes.c_uint32),
        ("stx_mnt_id", ctypes.c_uint64),  # Linux 5.8
        ("stx_dio_mem_align", ctypes.c_uint32), ("stx_dio_offset_align", ctypes.c_uint32),  # 6.1
        ("stx_subvol", ctypes.c_uint64),  # 6.10
        ("_spare3", ctypes.c_uint64 * 11),
    ]


def _load_statx():
    # statx is Linux's; elsewhere os.lstat serves (Windows has st_birthtime natively,
    # and ctypes.CDLL(None) raises TypeError there).
    if sys.platform != "linux":
        return None
    try:
        fn = ctypes.CDLL(None, use_errno=True).statx
    except (OSError, AttributeError):
        return None
    fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_uint, ctypes.POINTER(_Statx)]
    fn.restype = ctypes.c_int
    return fn


_statx = _load_statx()


class StatxResult:
    """The st_* attributes os.lstat gives, plus st_birthtime when the filesystem has one."""

    def __init__(self, sx: _Statx) -> None:
        def ns(ts: _Timestamp) -> int:
            return ts.tv_sec * 1_000_000_000 + ts.tv_nsec

        self.st_mode = sx.stx_mode
        self.st_ino = sx.stx_ino
        self.st_dev = os.makedev(sx.stx_dev_major, sx.stx_dev_minor)
        self.st_nlink = sx.stx_nlink
        self.st_uid = sx.stx_uid
        self.st_gid = sx.stx_gid
        self.st_size = sx.stx_size
        self.st_blocks = sx.stx_blocks
        self.st_blksize = sx.stx_blksize
        self.st_rdev = os.makedev(sx.stx_rdev_major, sx.stx_rdev_minor)
        self.st_atime_ns = ns(sx.stx_atime)
        self.st_mtime_ns = ns(sx.stx_mtime)
        self.st_ctime_ns = ns(sx.stx_ctime)
        self.st_atime = self.st_atime_ns / 1e9
        self.st_mtime = self.st_mtime_ns / 1e9
        self.st_ctime = self.st_ctime_ns / 1e9
        # Save-it-all (Indaleko's st_* introspection): every statx field, as
        # st_statx_*, so _full_stat_dump keeps what lstat cannot give
        # (attributes, mount id, ...). Timestamps as nanoseconds.
        for name, _ in sx._fields_:
            if not name.startswith("_"):
                value = getattr(sx, name)
                setattr(self, "st_statx_" + name.removeprefix("stx_"),
                        ns(value) if isinstance(value, _Timestamp) else value)
        if sx.stx_mask & _STATX_BTIME:
            self.st_birthtime_ns = ns(sx.stx_btime)
            self.st_birthtime = self.st_birthtime_ns / 1e9


def lstat_with_btime(path) -> StatxResult | os.stat_result:
    """os.lstat, plus st_birthtime where statx and the filesystem provide it."""
    if _statx is None:
        return os.lstat(path)
    buf = _Statx()
    encoded = os.fsencode(path)
    if _statx(_AT_FDCWD, encoded, _AT_SYMLINK_NOFOLLOW, _STATX_REQUEST, ctypes.byref(buf)) != 0:
        err = ctypes.get_errno()
        if err == errno.ENOSYS:
            return os.lstat(path)
        raise OSError(err, os.strerror(err), os.fsdecode(encoded))
    return StatxResult(buf)

"""Bounded decoded images and generated, confined filesystem storage."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
import uuid
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 20_000_000
FORM_LIMIT = MAX_BYTES + 65536
FORMATS = {'JPEG': ('jpg', 'image/jpeg'), 'PNG': ('png', 'image/png'), 'WEBP': ('webp', 'image/webp')}


class ImageInputError(Exception):
    pass


class ImageStorageError(Exception):
    pass


@dataclass
class CanonicalImage:
    data: bytes
    extension: str
    media_type: str


def canonical_image(raw):
    if len(raw) > MAX_BYTES:
        raise ImageInputError('Image exceeds five MiB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as probe:
                if probe.format not in FORMATS or probe.width * probe.height > MAX_PIXELS:
                    raise ImageInputError('Unsupported image or pixel limit exceeded')
                image_format = probe.format
                probe.verify()
            with Image.open(BytesIO(raw)) as decoded:
                decoded.load()
                oriented = ImageOps.exif_transpose(decoded)
                mode = 'RGB' if image_format == 'JPEG' else 'RGBA'
                pixels = oriented.convert(mode)
                # Construct a fresh image so metadata cannot follow the source.
                clean = Image.frombytes(mode, pixels.size, pixels.tobytes())
                output = BytesIO()
                clean.save(output, format=image_format)
        extension, media_type = FORMATS[image_format]
        return CanonicalImage(output.getvalue(), extension, media_type)
    except ImageInputError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise ImageInputError('Image content is invalid') from None


class ImageStorage:
    def __init__(self, root, namespace='avatars'):
        if namespace not in {'avatars','listings'}:raise ImageStorageError('Storage namespace is invalid')
        self.namespace = namespace
        self.root = Path(root).absolute()

    def path(self, relative, owner):
        if not isinstance(relative, str) or not re.fullmatch(rf'{self.namespace}/{owner}/[0-9a-f]{{32}}\.(jpg|png|webp)', relative):
            raise ImageStorageError('Stored image path is invalid')
        candidate = self.root / relative
        try:
            if self.root.is_symlink() or self.root.resolve() != self.root:
                raise ImageStorageError('Upload root is unsafe')
            for path in [self.root / self.namespace, self.root / self.namespace / str(owner), candidate]:
                if path.is_symlink() or path.resolve() != path:
                    raise ImageStorageError('Image path is unsafe')
                path.resolve().relative_to(self.root)
        except (OSError, ValueError, RuntimeError):
            raise ImageStorageError('Image path is unsafe') from None
        return candidate

    def write(self, image, owner):
        relative = f'{self.namespace}/{owner}/{uuid.uuid4().hex}.{image.extension}'
        path = self.path(relative, owner)
        created_file = False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path = self.path(relative, owner)
            with path.open('xb') as handle:
                created_file = True
                handle.write(image.data)
            return relative
        except OSError:
            if created_file:
                try:
                    self.delete(relative, owner)
                except ImageStorageError:
                    pass
            raise ImageStorageError('Image storage is unavailable') from None

    def read(self, relative, owner):
        path = self.path(relative, owner)
        try:
            return path.read_bytes(), {'jpg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}[path.suffix[1:]]
        except FileNotFoundError:
            return None
        except OSError:
            raise ImageStorageError('Image storage is unavailable') from None

    def delete(self, relative, owner):
        path = self.path(relative, owner)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            raise ImageStorageError('Image cleanup is unavailable') from None

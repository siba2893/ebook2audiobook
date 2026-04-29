"""
Generate assets/sample.epub — a minimal valid EPUB used for testing ebook2audiobook.
Run from the project root:  python tools/gen_sample_epub.py
"""
import os
import zipfile

OUT = os.path.join(os.path.dirname(__file__), '..', 'assets', 'sample.epub')
OUT = os.path.normpath(OUT)

SYNOPSIS = (
    "Todo buen rey necesita alguien que se encargue de sus asuntos mas turbios, "
    "máxime en tiempos revueltos, como los que corren en los Seis Ducados con los "
    "Corsarios de la Vela Roja saqueando sus costas. Pero ¿quién iba a pensar que "
    "el pequeno Traspie, hijo bastardo del rey Hidalgo y hasta entonces ayudante de "
    "caballerizo, podría ser esa persona?. Y si lo fuese, ¿podrá hacer compatibles "
    "la necesaria instrucción en el arte del asesinato con los valores de la amistad "
    "y honor en los que ha sido educado?."
)

MIMETYPE = "application/epub+zip"

CONTAINER = """\
<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf"
              media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

OPF = """\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"
         unique-identifier="BookID" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>Aprendiz de Asesino — Muestra</dc:title>
    <dc:creator opf:role="aut">Robin Hobb</dc:creator>
    <dc:language>es</dc:language>
    <dc:description>{synopsis}</dc:description>
    <dc:identifier id="BookID">ebook2audiobook-sample</dc:identifier>
  </metadata>
  <manifest>
    <item id="ncx"  href="toc.ncx"        media-type="application/x-dtbncx+xml"/>
    <item id="css"  href="Styles/style.css" media-type="text/css"/>
    <item id="ch01" href="Text/ch01.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="ch01"/>
  </spine>
</package>""".format(synopsis=SYNOPSIS.replace("&", "&amp;"))

NCX = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN"
  "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="ebook2audiobook-sample"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>Aprendiz de Asesino — Muestra</text></docTitle>
  <navMap>
    <navPoint id="ch01" playOrder="1">
      <navLabel><text>Capítulo 1: La Primera Historia</text></navLabel>
      <content src="Text/ch01.xhtml"/>
    </navPoint>
  </navMap>
</ncx>"""

CSS = """\
body { font-family: serif; margin: 2em; line-height: 1.6; }
h1   { font-size: 1.4em; margin-bottom: 1em; }
p    { text-indent: 1.5em; margin: 0 0 0.5em 0; }
"""

CHAPTER = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
  "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="es">
<head>
  <title>Capítulo 1: La Primera Historia</title>
  <link rel="stylesheet" type="text/css" href="../Styles/style.css"/>
</head>
<body>
  <h1>Capítulo 1: La Primera Historia</h1>
  <p>
    Todo buen rey necesita alguien que se encargue de sus asuntos mas turbios,
    máxime en tiempos revueltos, como los que corren en los Seis Ducados con los
    Corsarios de la Vela Roja saqueando sus costas.
  </p>
  <p>
    Pero ¿quién iba a pensar que el pequeno Traspie, hijo bastardo del rey Hidalgo
    y hasta entonces ayudante de caballerizo, podría ser esa persona?.
  </p>
  <p>
    Y si lo fuese, ¿podrá hacer compatibles la necesaria instrucción en el arte del
    asesinato con los valores de la amistad y honor en los que ha sido educado?.
  </p>
</body>
</html>"""


def build():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('mimetype',                    MIMETYPE, compress_type=zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml',      CONTAINER)
        z.writestr('OEBPS/content.opf',           OPF)
        z.writestr('OEBPS/toc.ncx',               NCX)
        z.writestr('OEBPS/Styles/style.css',      CSS)
        z.writestr('OEBPS/Text/ch01.xhtml',       CHAPTER)
    print(f"Created: {OUT}  ({os.path.getsize(OUT):,} bytes)")


if __name__ == '__main__':
    build()

# Bundled reflow test font

`LiberationSans-Regular.ttf` is the unmodified Liberation Sans Regular font from the official
Liberation Fonts 2.1.5 binary release:

- source: https://github.com/liberationfonts/liberation-fonts/releases/tag/2.1.5
- archive: `liberation-fonts-ttf-2.1.5.tar.gz`
- font SHA-256: `76D04C18EA243F426B7DE1F3AD208E927008F961DC5945E5AAD352D0DFDE8EE8`
- license: SIL Open Font License 1.1; see `OFL.txt`

The production reflow tests use this repository-owned file so Windows and Linux exercise identical
font bytes and pagination metrics. Production font selection is unchanged.

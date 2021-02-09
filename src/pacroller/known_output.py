from pacroller.config import KNOWN_OUTPUT_OVERRIDE
KNOWN_HOOK_OUTPUT_OVERRIDE, KNOWN_PACKAGE_OUTPUT_OVERRIDE = KNOWN_OUTPUT_OVERRIDE

KNOWN_HOOK_OUTPUT = {
    '': [],
    '20-systemd-sysusers.hook': [
        r'(?i)creating group .+',
        r'(?i)creating user .+',
    ],
    '30-systemd-sysctl.hook': [
        r'Not setting (.+) \(explicit setting exists\)\.',
    ],
    '90-mkinitcpio-install.hook': [
        r'==> Building image from preset: .+',
        r'==> Starting build: .+',
        r'==> WARNING: Possibly missing firmware for module: .+',
        r'==> Generating module dependencies',
        r'==> Creating (?:.+)-compressed initcpio image: .+',
        r'==> Image generation successful.*',
        r'[ ]+-> .+',
    ],
    **KNOWN_HOOK_OUTPUT_OVERRIDE
}

_keyring_output = [
    r'==> Appending keys from .+',
    r'==> Locally signing trusted keys in keyring\.\.\.',
    r'==> Importing owner trust values\.\.\.',
    r'==> Disabling revoked keys in keyring\.\.\.',
    r'==> Updating trust database\.\.\.',
    r'gpg: next trustdb check due at .+',
    r'gpg: public key .+ is .+ than the signature',
    r'gpg: Warning: using insecure memory!',
    r'[ ]+-> .+',
]

KNOWN_PACKAGE_OUTPUT = {
    '': [],
    'archlinux-keyring': _keyring_output,
    'archlinuxcn-keyring': [
        *_keyring_output,
        r'gpg: marginals needed:.+ completes needed:.+ trust model: pgp',
        r'gpg: depth:.+ valid:.+ signed:.+ trust:.+, .+, .+, .+, .+, .+',
    ],
    'brltty': [
        r'Please add your user to the brlapi group\.',
    ],
    'glibc': [
        r'Generating locales\.\.\.',
        r'Generation complete\.',
        r'  .*_.*\.\.\. done',
    ],
    **KNOWN_PACKAGE_OUTPUT_OVERRIDE
}

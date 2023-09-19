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
    '30-systemd-udev-reload.hook': [
        r'[ ][ ]Skipped: Device manager is not running\.',
    ],
    '90-mkinitcpio-install.hook': [
        r'==> Building image from preset: .+',
        r'==> Starting build: .+',
        r'==> WARNING: Possibly missing firmware for module: .+',
        r'==> Generating module dependencies',
        r'==> Creating (?:.+)-compressed initcpio image: .+',
        r'==> Image generation successful.*',
        r'[ ]+-> .+',
        r'ssh-.* .*',
        r'==> Using configuration file: .+',
        r'==> Using default configuration file: .+',
        r'==> WARNING: consolefont: no font found in configuration',
    ],
    '70-dkms-install.hook': [
        r'==> dkms install --no-depmod [^ ]+ -k [^ ]+',
        r'==> depmod [^ ]+',
    ],
    '71-dkms-remove.hook': [
        r'==> dkms remove [^ ]+',
        r'==> dkms remove --no-depmod [^ ]+ -k [^ ]+',
        r'==> depmod [^ ]+',
    ],
    '70-dkms-upgrade.hook': [
        r'==> dkms remove [^ ]+',
        r'==> dkms remove --no-depmod [^ ]+ -k [^ ]+',
        r'==> depmod [^ ]+',
    ],
    '90-update-appstream-cache.hook': [
        r'✔ Metadata cache was updated successfully\.',
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
    r'gpg: checking the trustdb',
    r'gpg: setting ownertrust to .+',
    r'gpg: marginals needed:.+ completes needed:.+ trust model: pgp',
    r'gpg: depth:.+ valid:.+ signed:.+ trust:.+, .+, .+, .+, .+, .+',
    r'gpg: key .+: no user ID for key signature packet of class .+',
    r'gpg: inserting ownertrust of .+',
    r'gpg: changing ownertrust from .+ to .+',
    r'[ ]+-> .+',
]

_vbox_output = [
    r'0%\.\.\.10%\.\.\.20%\.\.\.30%\.\.\.40%\.\.\.50%\.\.\.60%\.\.\.70%\.\.\.80%\.\.\.90%\.\.\.100%',
]

KNOWN_PACKAGE_OUTPUT = {
    '': [],
    'archlinux-keyring': _keyring_output,
    'archlinuxcn-keyring': _keyring_output,
    'brltty': [
        r'Please add your user to the brlapi group\.',
    ],
    'glibc': [
        r'Generating locales\.\.\.',
        r'Generation complete\.',
        r'  .*_.*\.\.\. done',
    ],
    'fontconfig': [
        r'Rebuilding fontconfig cache\.\.\.',
    ],
    'lib32-fontconfig': [
        r'Rebuilding 32-bit fontconfig cache\.\.\.',
    ],
    'virtualbox': _vbox_output,
    'virtualbox-ext-oracle': _vbox_output,
    'virtualbox-ext-vnc': _vbox_output,
    'virtualbox-ext-vnc-svn': _vbox_output,
    'tor-browser': [
        r'$',
        {'action': ['upgrade'], 'regex': r'==> The copy of Tor Browser in your home directory will be upgraded at the'},
        {'action': ['upgrade'], 'regex': r'==> first time you run it as your normal user\. Just start it and have fun!'},
    ],
    'grub': [
        {'action': ['upgrade'], 'regex': r':: To use the new features provided in this GRUB update, it is recommended'},
        {'action': ['upgrade'], 'regex': r'   to install it to the MBR or UEFI\. Due to potential configuration'},
        {'action': ['upgrade'], 'regex': r'   incompatibilities, it is advised to run both, installation and generation'},
        {'action': ['upgrade'], 'regex': r'   of configuration:'},
        {'action': ['upgrade'], 'regex': r'     \$ grub-install \.\.\.'},
        {'action': ['upgrade'], 'regex': r'     \$ grub-mkconfig -o /boot/grub/grub\.cfg'},
    ],
    'nvidia-utils': [
        {'action': ['upgrade'], 'regex': r'If you run into trouble with CUDA not being available, run nvidia-modprobe first\.'},
        {'action': ['upgrade'], 'regex': r'If you use GDM on Wayland, you might have to run systemctl enable --now nvidia-resume\.service'},
    ],
    **KNOWN_PACKAGE_OUTPUT_OVERRIDE
}

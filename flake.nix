{
  description = "Pi-Lite EQ meter: 14-band spectrum from a USB mic on a Raspberry Pi";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs =
    { self, nixpkgs, ... }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      packages = forAll (pkgs: {
        default = pkgs.callPackage ./nix/package.nix { };
      });

      nixosModules.default = import ./nix/module.nix self;

      devShells = forAll (pkgs: {
        default = pkgs.mkShell {
          packages = [
            pkgs.alsa-utils
            (pkgs.python3.withPackages (ps: [ ps.numpy ps.pyserial ps.pytest ]))
          ];
        };
      });
    };
}

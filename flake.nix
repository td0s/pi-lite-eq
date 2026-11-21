{
  description = "Pi-Lite EQ meter: 14-band spectrum from a USB mic on a Raspberry Pi";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs =
    { self, nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        packages = [
          pkgs.alsa-utils
          (pkgs.python3.withPackages (ps: [
            ps.numpy
            ps.pyserial
            ps.pytest
          ]))
        ];
      };
    };
}

{ lib, python3, alsa-utils, makeWrapper, stdenvNoCC }:

let
  python = python3.withPackages (ps: [ ps.numpy ps.pyserial ]);
in
stdenvNoCC.mkDerivation {
  pname = "pilite-eq";
  version = "0.1.0";

  src = lib.fileset.toSource {
    root = ../.;
    fileset = ../pilite_eq;
  };

  nativeBuildInputs = [ makeWrapper ];

  installPhase = ''
    runHook preInstall
    mkdir -p $out/lib/pilite-eq $out/bin
    cp -r pilite_eq $out/lib/pilite-eq/
    makeWrapper ${python.interpreter} $out/bin/pilite-eq \
      --add-flags "-m pilite_eq" \
      --prefix PYTHONPATH : $out/lib/pilite-eq \
      --prefix PATH : ${lib.makeBinPath [ alsa-utils ]}
    runHook postInstall
  '';

  meta = {
    description = "14-band EQ meter on a Ciseco Pi-Lite, from a USB mic";
    mainProgram = "pilite-eq";
    platforms = lib.platforms.linux;
  };
}

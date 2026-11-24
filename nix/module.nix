# NixOS module: services.pilite-eq
self:
{ config, lib, pkgs, ... }:

let
  cfg = config.services.pilite-eq;
in
{
  options.services.pilite-eq = {
    enable = lib.mkEnableOption "the Pi-Lite EQ meter";

    package = lib.mkOption {
      type = lib.types.package;
      default = self.packages.${pkgs.stdenv.hostPlatform.system}.default;
      defaultText = lib.literalExpression "pi-lite-eq.packages.\${system}.default";
      description = "The pilite-eq package to run.";
    };

    port = lib.mkOption {
      type = lib.types.str;
      default = "/dev/ttyAMA0";
      description = "Serial port the Pi-Lite is on.";
    };

    device = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      example = "plughw:CARD=Device,DEV=0";
      description = "ALSA capture device. Null picks the first USB mic.";
    };

    extraArgs = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      example = [ "--flip-x" "--range" "35" ];
      description = "Extra command-line options (see the README's Options table).";
    };
  };

  config = lib.mkIf cfg.enable {
    # Only one program can hold the serial port.
    systemd.services."serial-getty@${baseNameOf cfg.port}".enable = false;

    systemd.services.pilite-eq = {
      description = "Pi-Lite EQ meter";
      wantedBy = [ "multi-user.target" ];
      after = [ "sound.target" ];
      serviceConfig = {
        ExecStart = lib.escapeShellArgs (
          [ (lib.getExe cfg.package) "--port" cfg.port ]
          ++ lib.optionals (cfg.device != null) [ "--device" cfg.device ]
          ++ cfg.extraArgs
        );
        DynamicUser = true;
        SupplementaryGroups = [ "dialout" "audio" ];
        # The USB mic can appear a few seconds after boot; just try again.
        Restart = "on-failure";
        RestartSec = 10;

        # Hardening: it only needs the serial port and the sound card.
        DevicePolicy = "closed";
        DeviceAllow = [ "${cfg.port} rw" "char-alsa rw" ];
        PrivateNetwork = true;
        ProtectHome = true;
        ProtectSystem = "strict";
        NoNewPrivileges = true;
      };
    };
  };
}

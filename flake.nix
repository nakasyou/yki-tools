{
  description = "Development environments for Yo-kai Watch U generation and research";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { nixpkgs, ... }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forEachSystem = nixpkgs.lib.genAttrs systems;
    in
    {
      devShells = forEachSystem (system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python313.withPackages (ps: [ ps.jsonschema ]);
          reliefPython = pkgs.python313.withPackages (ps: with ps; [
            jsonschema numpy pillow scipy shapely trimesh mapbox-earcut
            manifold3d matplotlib
          ]);
          depthPython = pkgs.python313.withPackages (ps: with ps; [
            jsonschema numpy pillow scipy shapely trimesh mapbox-earcut
            manifold3d matplotlib torch transformers
          ]);
          mkDevShell = pythonEnv: extraPackages: pkgs.mkShell {
            packages = [ pythonEnv pkgs.uv pkgs.ffmpeg pkgs.openscad pkgs.stdenv.cc ]
              ++ extraPackages;
            # Use Nix's interpreter instead of downloading a managed Python.
            UV_PYTHON = "${pythonEnv}/bin/python3";
            UV_PYTHON_DOWNLOADS = "never";
          };
        in
        {
          default = mkDevShell python [ ];
          relief = mkDevShell reliefPython [ pkgs.blender ];
          depth = mkDevShell depthPython [ pkgs.blender ];
        });
    };
}

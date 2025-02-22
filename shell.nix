{ python ? "3.9" }:
let
  pkgs = import ./nix;

  devDeps = with pkgs; [
    cacert
    cachix
    commitlint
    curl
    git
    niv
    nix-linter
    nixpkgs-fmt
    poetry
    pre-commit
    prettierTOML
    shellcheck
    shfmt
  ];

  impalaUdfDeps = with pkgs; [
    boost
    clang_12
    cmake
  ];

  backendTestDeps = [ pkgs.docker-compose ];
  vizDeps = [ pkgs.graphviz-nox ];
  pysparkDeps = [ pkgs.openjdk11 ];
  docDeps = [ pkgs.pandoc ];

  # postgresql is the client, not the server
  postgresDeps = [ pkgs.postgresql ];
  geospatialDeps = with pkgs; [ gdal proj ];

  sqliteDeps = [ pkgs.sqlite-interactive ];

  libraryDevDeps = impalaUdfDeps
    ++ backendTestDeps
    ++ vizDeps
    ++ pysparkDeps
    ++ docDeps
    ++ geospatialDeps
    ++ postgresDeps
    ++ sqliteDeps;

  pythonShortVersion = builtins.replaceStrings [ "." ] [ "" ] python;
in
pkgs.mkShell {
  name = "ibis${pythonShortVersion}";

  shellHook = ''
    data_dir="$PWD/ci/ibis-testing-data"
    mkdir -p "$data_dir"
    chmod u+rwx "$data_dir"
    cp -rf ${pkgs.ibisTestingData}/* "$data_dir"
    chmod --recursive u+rw "$data_dir"

    export IBIS_TEST_DATA_DIRECTORY="$data_dir"
  '';

  buildInputs = devDeps ++ libraryDevDeps ++ [
    pkgs."ibisDevEnv${pythonShortVersion}"
  ];

  PYTHONPATH = builtins.toPath ./.;
}

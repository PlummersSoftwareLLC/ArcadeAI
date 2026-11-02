# Manual setup on ubvmdell

Robotron lives in the ArcadeAI repository. From a fresh checkout:

```bash
./Robotron/setup.sh
```

Python 3.11+, a C compiler, and MAME with Lua support are required. On Ubuntu,
the system packages are `python3-venv`, `build-essential`, `mame`, and `zstd`.
The setup script creates `.venv` at the repository root. It installs dependencies
only: it does not launch training, install services, or enable autostart.
Use `ROBOTRON_SETUP_PYTHON` to select Python. Set `ROBOTRON_TORCH_INDEX` to an
appropriate official PyTorch wheel index if the default wheel is unsuitable
for the target GPU or driver. The historical `requirements-gb300.lock` is an
environment record; it includes an ARM/free-threaded wheel and is not a portable
installation requirements file.

Models, replay arrays, logs, and locally staged ROMs are separate data, not Git
source. Preserve them when moving hosts. The final GB300 shutdown bundle contains
the latest online/target/Adam checkpoint, the full replay ring, selected HOF and
EpHOF generations, settings/control files, and the protected champion. Keep the
protected champion distinct from the unqualified latest training policy.

Restore that bundle into `Robotron/` on a disk with enough free space, then verify
its manifest hashes. Its `models_dqn/robotron_dqn_latest_replay` directory is
disk-backed; do not copy old absolute `/dev/shm` paths or systemd overrides from
Dell. Historical held-startup jobs and cohort authorizations are single-use and
must not be reused. The research tools contain archived, host-specific experiments;
they are retained as source, not an automatic migration procedure.

For an intentional manual trainer launch after reviewing hardware and settings:

```bash
cd Robotron
CUDA_VISIBLE_DEVICES=0 ./starttrainer.sh
```

Choose replay/batch/population sizes to fit the new machine before launching.
The former 192-actor workload and 6-million-transition replay require substantial
RAM and storage. A smaller target may be suitable for inference but unable to
resume that full training configuration. No training launch is part of setup.

MAME clients must explicitly select the new host:

```bash
./startmame.sh --fg --eval --level 29 --socket-host ubvmdell --socket-port 9999
```

Port 9999 requires a separately started frozen play endpoint; 9998 is the training
transport. The launch command alone does not start either server. Native sum-tree
code compiles locally on first use. Do not copy `.so` files or virtual environments
between CPU architectures.

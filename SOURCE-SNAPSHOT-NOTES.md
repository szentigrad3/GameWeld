# PC1 source snapshot provenance

- This branch descends from 0.8.0 development `main` for Git history purposes, but its application files were replaced with the 0.7.0 PC1 source snapshot.
- The snapshot was prepared from historical `gameweld-0.7.0-source.zip` and common project files in the curated GitHub repository.
- PC1 changes remove the converted Resonance native trainer source and the game reference art, and make the corresponding native profiles fail closed.
- Source includes the PC1-specific packaging script and regression tests. The verified original stable AppImage remains unchanged.
- The original stable binary **contained** game-specific reference assets and a converted native trainer. Those components are deliberately excluded from the PC1 candidate, which is not yet approved for public redistribution.
- Repacking an inherited AppImage is **not** a bit-identical, independently reproducible source build.
- No `v0.7.0` tag or GitHub binary release has been created from this branch.

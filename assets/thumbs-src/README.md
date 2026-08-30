Hand-made card art for /work/.

Drop `<entry-id>.png` (or .jpg) here and it overrides the thumbnail the
generator would otherwise crop out of the entry's poster or video.

  - square, 1:1 - the card crops to a square either way
  - 600x600 or larger; the build downsamples to 288 and picks a JPEG quality
  - the picture area is 90 CSS px, so: one subject filling the frame,
    no small text, nothing essential in the corners (they're rounded off)

Only entries that lead the index need one - those with a body in
_work_bodies/. See _data/featured.json for the current set.

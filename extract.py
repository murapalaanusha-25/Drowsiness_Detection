import bz2

with open('shape_predictor_68_face_landmarks.dat.bz2', 'rb') as f_in:
    with open('shape_predictor_68_face_landmarks.dat', 'wb') as f_out:
        f_out.write(bz2.decompress(f_in.read()))

print("Extraction complete.")
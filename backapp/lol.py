from PIL import Image
import numpy as np

arr = np.random.randint(0,255,(100,100,3))
im = Image.fromarray(arr,'RGB')
im.show()


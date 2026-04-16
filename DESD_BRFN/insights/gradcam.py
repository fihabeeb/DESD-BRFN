import numpy as np
import tensorflow as tf
import cv2
import base64
from io import BytesIO
from PIL import Image

# Last convolutional layer from your model summary
LAST_CONV_LAYER = "conv2d_3"


def generate_gradcam(model, img_array, class_index):
    """
    Generate a Grad-CAM heatmap for the given class index using the condition head.
    """
    # model.output[0] = condition head (since your model has 3 outputs)
    grad_model = tf.keras.models.Model(
        [model.inputs],
        [model.get_layer(LAST_CONV_LAYER).output, model.output[0]]
    )

    with tf.GradientTape() as tape:
        conv_outputs, predictions = grad_model(img_array)
        loss = predictions[:, class_index]

    grads = tape.gradient(loss, conv_outputs)
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))

    conv_outputs = conv_outputs[0]
    heatmap = tf.reduce_sum(tf.multiply(pooled_grads, conv_outputs), axis=-1)

    heatmap = np.maximum(heatmap, 0)
    heatmap /= np.max(heatmap) + 1e-8

    return heatmap


def overlay_heatmap(heatmap, image):
    """
    Overlay the Grad-CAM heatmap on top of the original image.
    """
    heatmap = cv2.resize(heatmap, (image.shape[1], image.shape[0]))
    heatmap = np.uint8(255 * heatmap)
    heatmap = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)

    overlay = cv2.addWeighted(image, 0.6, heatmap, 0.4, 0)
    return overlay


def to_base64(img_array):
    """
    Convert a NumPy image array (H, W, C) to a base64 PNG string.
    """
    img = Image.fromarray(img_array)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

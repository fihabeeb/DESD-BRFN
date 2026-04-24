import base64
from io import BytesIO

import cv2
import numpy as np
import tensorflow as tf
from PIL import Image

LAST_CONV_LAYER = "conv2d_3"


def generate_gradcam(model, img_array, class_index):
    grad_model = tf.keras.models.Model(
        model.inputs,
        [model.get_layer(LAST_CONV_LAYER).output, model.output[0]],
    )

    with tf.GradientTape() as tape:
        conv_outputs, predictions = grad_model(img_array, training=False)
        loss = predictions[:, class_index]

    grads = tape.gradient(loss, conv_outputs)
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))

    conv_outputs = conv_outputs[0]
    heatmap = tf.reduce_sum(tf.multiply(pooled_grads, conv_outputs), axis=-1).numpy()
    heatmap -= heatmap.min()
    heatmap /= heatmap.max() + 1e-8

    return heatmap


def colorize_heatmap(heatmap):
    """Apply JET colormap to a 2D heatmap and return an RGB array."""
    colored = cv2.applyColorMap(np.uint8(255 * heatmap), cv2.COLORMAP_JET)
    return cv2.cvtColor(colored, cv2.COLOR_BGR2RGB)


def overlay_heatmap(heatmap, image):
    resized = cv2.resize(heatmap, (image.shape[1], image.shape[0]))
    heatmap_rgb = colorize_heatmap(resized)
    return cv2.addWeighted(image, 0.6, heatmap_rgb, 0.4, 0)


def to_base64(img_array):
    img = Image.fromarray(img_array)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

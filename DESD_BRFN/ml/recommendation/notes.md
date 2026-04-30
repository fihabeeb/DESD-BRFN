# task 1

System can analyze purchase history predict frequently order items and provide quick re-order options

Latest benchemark
352/352 ━━━━━━━━━━━━━━━━━━━━ 2s 5ms/step - binary_accuracy: 0.9864 - loss: 0.0195 - precision: 0.2099 - recall: 0.3815 - val_binary_accuracy: 0.9865 - val_loss: 0.0195 - val_precision: 0.2032 - val_recall: 0.3776 - learning_rate: 0.0010
Restoring model weights from the end of the best epoch: 25.

Validation: loss=0.0195, binary_accuracy=0.9865, precision=0.2032, recall=0.3776
Mean AP (per-class): 0.0573
Label Ranking AP: 0.4455
Saving model to ml/recommendation/final/sigmoid_lstm.keras

Tried: 
- stackedLSTM + user embedding (sigmoid, BinarcyFocalCrossentropy)

# ignore below 

## Single LSTM
352/352 ━━━━━━━━━━━━━━━━━━━━ 1s 2ms/step - binary_accuracy: 0.9865 - loss: 0.0193 - precision: 0.1784 - recall: 0.2995 - val_binary_accuracy: 0.9868 - val_loss: 0.0191 - val_precision: 0.1787 - val_recall: 0.3043 - learning_rate: 5.0000e-04
Restoring model weights from the end of the best epoch: 25.

Validation: loss=0.0191, binary_accuracy=0.9868, precision=0.1787, recall=0.3043
Mean AP (per-class): 0.0418
Label Ranking AP: 0.3610
Saving model to ml/recommendation/final/sigmoid_lstm.keras

## Bidirectional LSTM
352/352 ━━━━━━━━━━━━━━━━━━━━ 1s 4ms/step - binary_accuracy: 0.9865 - loss: 0.0190 - precision: 0.1830 - recall: 0.3073 - val_binary_accuracy: 0.9868 - val_loss: 0.0191 - val_precision: 0.1820 - val_recall: 0.3100 - learning_rate: 5.0000e-04
Restoring model weights from the end of the best epoch: 24.

Validation: loss=0.0191, binary_accuracy=0.9868, precision=0.1818, recall=0.3096
Mean AP (per-class): 0.0439
Label Ranking AP: 0.3653
Saving model to ml/recommendation/final/sigmoid_lstm.keras



# new approach

## product output=64
### With 2 lstm stacked (128 + 64)
352/352 ━━━━━━━━━━━━━━━━━━━━ 2s 6ms/step - binary_accuracy: 0.9899 - loss: 0.0168 - precision: 0.0637 - recall: 0.0951 - val_binary_accuracy: 0.9902 - val_loss: 0.0162 - val_precision: 0.0670 - val_recall: 0.1028 - learning_rate: 5.0000e-04
Restoring model weights from the end of the best epoch: 25.

Validation: loss=0.0162, binary_accuracy=0.9902, precision=0.0670, recall=0.1028
Mean AP (per-class): 0.0419
Label Ranking AP: 0.1001

### with 2 lstm stacked (64 + 32)
352/352 ━━━━━━━━━━━━━━━━━━━━ 1s 3ms/step - binary_accuracy: 0.9899 - loss: 0.0167 - precision: 0.0650 - recall: 0.0970 - val_binary_accuracy: 0.9902 - val_loss: 0.0163 - val_precision: 0.0658 - val_recall: 0.1011 - learning_rate: 5.0000e-04
Restoring model weights from the end of the best epoch: 24.

Validation: loss=0.0162, binary_accuracy=0.9902, precision=0.0659, recall=0.1012
Mean AP (per-class): 0.0387
Label Ranking AP: 0.1002

## product ouput = 32
352/352 ━━━━━━━━━━━━━━━━━━━━ 1s 3ms/step - binary_accuracy: 0.9899 - loss: 0.0165 - precision: 0.0693 - recall: 0.1035 - val_binary_accuracy: 0.9902 - val_loss: 0.0162 - val_precision: 0.0721 - val_recall: 0.1107 - learning_rate: 5.0000e-04
Restoring model weights from the end of the best epoch: 24.

Validation: loss=0.0162, binary_accuracy=0.9902, precision=0.0705, recall=0.1082
Mean AP (per-class): 0.0409
Label Ranking AP: 0.1022




# 24/4
==================================================
EVALUATION (V5)
==================================================

Hit Rates:
  @1:  0.0234
  @3:  0.0580
  @5:  0.0851
  @10: 0.1462

Top-K Accuracy:
  Top-1: 0.0234
  Top-3: 0.0580
  Top-5: 0.0851
  Top-10: 0.1462


==================================================
EVALUATION (v5.1)
==================================================

Sample attention weights (first 5): [0.00689181 0.00669269 0.00643798 0.00603998 0.00943034]

Hit Rates:
  @1:  0.0339
  @3:  0.0796
  @5:  0.1258
  @10: 0.1888

Top-K Accuracy:
  Top-1: 0.0339
  Top-3: 0.0796
  Top-5: 0.1258
  Top-10: 0.1888
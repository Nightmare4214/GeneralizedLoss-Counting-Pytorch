# A Generalized Loss Function for Crowd Counting and Localization

## Data

Dowload Dataset UCF-QNRF [Link](https://www.crcv.ucf.edu/data/ucf-qnrf/)  
Download Shanghai Tech Part A and Part B[Link](https://www.kaggle.com/tthien/shanghaitech)  
Download NWPU[Link](https://www.crowdbenchmark.com/nwpucrowd.html)  

## Data preparation

### UCF-QNRF
```bash
python preprocess_dataset.py --origin_dir PATH_TO_ORIGIN_DATASET --data_dir PATH_TO_DATASET
```

### Shanghai Tech

```bash
python preprocess_shanghai.py --origin_dir PATH_TO_ORIGIN_DATASET --data_dir PATH_TO_DATASET --part 'A'
```

[//]: # (The dataset can be constructed followed by [Bayesian Loss]&#40;https://github.com/ZhihengCV/Bayesian-Crowd-Counting&#41;.)

## Pretrained model
The pretrained model can be downloaded from [GoogleDrive](https://drive.google.com/drive/folders/1TJF2IeFPoeLzqNXKXXXK8nPH62HijZaS?usp=sharing).  
Final Test: mae 85.09911092883813, mse 150.88815648865386  

paper:  mae 84.3, mse 147.5  
## Test

```bash
python test.py --data_dir PATH_TO_DATASET --save_dir PATH_TO_CHECKPOINT
```

## Train

```bash
python train.py --data_dir PATH_TO_DATASET --save_dir PATH_TO_CHECKPOINT
```

## Reproduction

### UCF-QNRF

mae: 84.3, mse: 147.5

| cost | scale | reach | blur  | scaling | tau | p | mae  | mse  |
|------|-------|-------|-------|---------|-----|---| ---- | ---- |
| per  | 0.6   | 0.5   | 0.01  | 0.5     | 0.1 | 1 | 90.85878733103861     | 164.81297964468203     |
| exp  | 0.6   | 0.5   | 0.01  | 0.5     | 0.1 | 1 | 85.69232401590861     | 155.30853159819492     |
| exp  | 0.6   | 0.5   | 0.005 | 0.5     | 0.5 | 1 | 94.7432665111062     |  169.12924529962544    |
| exp  | 0.6   | 0.5   | 0.01  | 0.5     | 0.5 | 1 | 90.37459440859492     | 160.29078877178213     |
| exp  | 0.6   | 0.5   | 0.005 | 0.5     | 0.1 | 1 | 92.81271439969183     | 172.55166210599293     |

### Shanghai-A

mae: 61.3, mse: 95.4

| cost | scale | reach | blur  | scaling | tau | p | mae  | mse  |
|------|-------|-------|-------|---------|-----|---| ---- | ---- |
| L2  | 0.6   | 0.5   | 0.01  | 0.5     | 0.1 | 1 | 73.4685192317753     | 108.96970748752973     |
| exp  | 0.6   | 0.5   | 0.01  | 0.5     | 0.1 | 1 | 69.52044338184399     | 115.7613994812161     |

### Shanghai-B

mae: 7.3, mse: 11.7

| cost | scale | reach | blur  | scaling | tau | p | mae  | mse  |
|------|-------|-------|-------|---------|-----|---| ---- | ---- |
| exp  | 0.6   | 0.5   | 0.01  | 0.5     | 0.1 | 1 | 8.174663287174853    | 13.731827122355636     |

### Citation
If you use our code or models in your research, please cite with:

```
@InProceedings{Wan_2021_CVPR,
    author    = {Wan, Jia and Liu, Ziquan and Chan, Antoni B.},
    title     = {A Generalized Loss Function for Crowd Counting and Localization},
    booktitle = {Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)},
    year      = {2021},
    pages     = {1974-1983}
}
```

### Acknowledgement
We use [GeomLoss](https://www.kernel-operations.io/geomloss/) package to compute transport matrix. Thanks for the authors for providing this fantastic tool. The code is slightly modified to adapt to our framework.

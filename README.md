# A Generalized Loss Function for Crowd Counting and Localization

## Data

Dowload Dataset UCF-QNRF [Link](https://www.crcv.ucf.edu/data/ucf-qnrf/)

## Data preparation

```
python preprocess_dataset.py --origin_dir PATH_TO_ORIGIN_DATASET --data_dir PATH_TO_DATASET
```
[//]: # (The dataset can be constructed followed by [Bayesian Loss]&#40;https://github.com/ZhihengCV/Bayesian-Crowd-Counting&#41;.)

## Pretrained model
The pretrained model can be downloaded from [GoogleDrive](https://drive.google.com/drive/folders/1TJF2IeFPoeLzqNXKXXXK8nPH62HijZaS?usp=sharing).  
Final Test: mae 85.09911092883813, mse 150.88815648865386  

paper:  mae 84.3, mse 147.5  
## Test

```
python test.py --data_dir PATH_TO_DATASET --save_dir PATH_TO_CHECKPOINT
```

## Train

```
python train.py --data_dir PATH_TO_DATASET --save_dir PATH_TO_CHECKPOINT
```

## Reproduction

--cost per --scale 0.6 --reach 0.5 --blur 0.01 --scaling 0.5 --tau 0.1 --p 1: Final Test: mae 90.85878733103861, mse 164.81297964468203  
--cost exp --scale 0.6 --reach 0.5 --blur 0.01 --scaling 0.5 --tau 0.1 --p 1: Final Test: mae 85.69232401590861, mse 155.30853159819492  
--cost exp --scale 0.6 --reach 0.5 --blur 0.005 --scaling 0.5 --tau 0.5 --p 1: Final Test: mae 94.7432665111062, mse 169.12924529962544  
--cost exp --scale 0.6 --reach 0.5 --blur 0.01 --scaling 0.5 --tau 0.5 --p 1: Final Test: mae 90.37459440859492, mse 160.29078877178213  
--cost exp --scale 0.6 --reach 0.5 --blur 0.005 --scaling 0.5 --tau 0.1 --p 1: Final Test: mae 92.81271439969183, mse 172.55166210599293

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

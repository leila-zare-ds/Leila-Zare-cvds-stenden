# Leila Zare – Computer Vision & Data Science

## About This Repository

This repository includes my Python exercises and coding practice as part of my application for the **MSc Computer Vision & Data Science programme at NHL Stenden University of Applied Sciences**.

## Exercises and What I Worked On

The notebook [`debugging_final.ipynb`](debugging_final.ipynb) includes four exercises that I worked through, corrected, and tested.

### Exercise 1 – Fruit ID Mapping (`id_to_fruit`)

In this exercise, I worked on a function that connects fruit IDs to their corresponding names.

The main problem was the use of a set, which does not guarantee the required order. I changed it to a list so that each ID refers to the correct fruit name. I also added a check to handle invalid IDs.

### Exercise 2 – Coordinate Swapping (`swap`)

This exercise was about working with coordinate data using NumPy.

I found some problems with the original indexing and assignment. I corrected the code by creating a copy of the original array and then swapping the x and y coordinates without changing the other values.

### Exercise 3 – Data Visualization (`plot_data`)

For this exercise, I worked with a CSV file containing Precision and Recall values and used Matplotlib to visualize the data.

I made the necessary corrections to read the data, convert the values into numbers, and create the plot with Precision on the x-axis and Recall on the y-axis. I also added the axis labels and adjusted the limits to make the chart easier to read.

### Exercise 4 – Generative Adversarial Network (GAN)

This exercise introduced me to a basic GAN implementation using the MNIST handwritten digit dataset.

The model contains two neural networks:

- **Generator:** Creates artificial handwritten digit images.
- **Discriminator:** Tries to distinguish real images from generated ones.

While reviewing the code, I identified and corrected two issues:

1. **Structural Bug – Batch Size:** The original code used a fixed batch size for generating random inputs and labels. This caused a mismatch when the last batch contained fewer samples than the specified batch size. I corrected this by using `real_samples.size(0)` to determine the actual size of the current batch dynamically. This ensures that the generated inputs and labels have matching dimensions.

2. **Cosmetic Bug – Image Display Condition:** The original condition used `n == batch_size - 1` to determine when to display generated images. I changed it to `n == len(train_loader) - 1`, so that the generated images are displayed at the end of each epoch.

**Testing and Results:**

I successfully executed the GAN training process using PyTorch and the MNIST dataset.

I tested the corrected implementation with two different batch sizes:

- `batch_size = 32`
- `batch_size = 64`

In both cases, the training completed successfully for 100 epochs without the previous batch-size error. The Generator also produced handwritten digit-like images based on the MNIST dataset.

## Tools and Libraries

During these exercises, I worked with the following tools and libraries:

- Python
- NumPy
- Matplotlib
- CSV module
- PyTorch (`torch`)
- TorchVision (`torchvision`)
- Jupyter Notebook

## Current Status

- **Exercise 1:** Corrected and tested successfully.
- **Exercise 2:** Corrected and tested successfully.
- **Exercise 3:** Corrected and tested successfully.
- **Exercise 4:** Structural and cosmetic issues corrected; training successfully completed and tested with batch sizes of 32 and 64.

## Final Remarks

Working on these exercises gave me an opportunity to practice Python and understand how to approach programming problems, find errors, and improve existing code.

I am particularly interested in developing my skills in data science, machine learning, image processing, and computer vision. I see these exercises as part of my preparation for further studies in this field.

---

**Author:** Leila Zare  
**Programme:** MSc Computer Vision & Data Science  
**Institution:** NHL Stenden University of Applied Sciences

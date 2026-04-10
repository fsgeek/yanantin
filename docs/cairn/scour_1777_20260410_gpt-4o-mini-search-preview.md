<!-- Chasqui Scour Tensor
     Run: 1777
     Model: openai/gpt-4o-mini-search-preview (OpenAI: GPT-4o-mini Search Preview)
     Target: src/yanantin/apacheta
     Scope: introspection
     Cost: prompt=$1.5e-07/M, completion=$6e-07/M
     Usage: {'prompt_tokens': 10177, 'completion_tokens': 453, 'total_tokens': 10630, 'cost': 0.02929835, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.02929835, 'upstream_inference_prompt_cost': 0.00152655, 'upstream_inference_completions_cost': 0.0002718}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-10T11:08:08.020540+00:00
     GenerationID: gen-1775819285-VjhZxB0nNxqyMrXQWU4W
-->

A tensor is a multi-dimensional array that generalizes scalars, vectors, and matrices to higher dimensions. In Python, tensors are fundamental in libraries like NumPy, PyTorch, and TensorFlow, which are widely used for numerical computations and machine learning tasks.

**Creating Tensors in Python:**

- **Using NumPy:**
  NumPy provides the `np.array()` function to create tensors from Python lists or tuples.

  ```python
  import numpy as np

  # Creating a 2D tensor (matrix)
  tensor_2d = np.array([[1, 2], [3, 4]])

  # Creating a 3D tensor
  tensor_3d = np.array([[[1, 2], [3, 4]], [[5, 6], [7, 8]]])
  ```

- **Using PyTorch:**
  PyTorch offers the `torch.tensor()` function to create tensors.

  ```python
  import torch

  # Creating a 2D tensor
  tensor_2d = torch.tensor([[1, 2], [3, 4]])

  # Creating a 3D tensor
  tensor_3d = torch.tensor([[[1, 2], [3, 4]], [[5, 6], [7, 8]]])
  ```

- **Using TensorFlow:**
  TensorFlow provides the `tf.convert_to_tensor()` function to convert Python objects to tensors.

  ```python
  import tensorflow as tf

  # Creating a 2D tensor
  tensor_2d = tf.convert_to_tensor([[1, 2], [3, 4]])

  # Creating a 3D tensor
  tensor_3d = tf.convert_to_tensor([[[1, 2], [3, 4]], [[5, 6], [7, 8]]])
  ```

**Tensor Operations:**

Once created, tensors can be manipulated using various operations such as addition, multiplication, and reshaping. These operations are optimized for performance, especially when utilizing hardware accelerators like GPUs.

Understanding tensors and their creation is essential for effective numerical computations and machine learning model development in Python. 
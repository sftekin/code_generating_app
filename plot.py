import pickle as pkl
import numpy as np
import matplotlib.pyplot as plt


with open("exec_time.pkl", "rb") as f:
    exec_time = pkl.load(f)

y_axis = np.array(exec_time)
x_axis = np.arange(1, len(exec_time)+1)

fig, ax = plt.subplots()
ax.plot(x_axis, y_axis, label="code completion time")
ax.yaxis.grid(color='gray', linestyle='dashed')
ax.set_xlim(1, len(x_axis)+1)
ax.set_yticks(np.arange(0, 61, 10))
ax.set_xlabel("Experiment")
ax.set_ylabel("Time (s)")
ax.legend()
plt.savefig("figures/exec_time.png", dpi=200, bbox_inches="tight")
plt.show()



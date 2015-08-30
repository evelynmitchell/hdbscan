# -*- coding: utf-8 -*-
"""
hdbscan.plots: Use matplotlib to display plots of internal 
               tree structures used by HDBSCAN.
"""
# Author: Leland McInnes <leland.mcinnes@gmail.com>
#
# License: BSD 3 clause

from ._hdbscan_tree import compute_stability

import numpy as np

CB_LEFT = 0
CB_RIGHT = 1
CB_BOTTOM = 2
CB_TOP = 3

def get_leaves(condensed_tree):
    cluster_tree = condensed_tree[condensed_tree['child_size'] > 1]
    clusters = cluster_tree['child']
    return [c for c in clusters if len(cluster_tree[cluster_tree['parent'] == c]) == 0]

def bfs_from_cluster_tree(tree, bfs_root):
    result = []
    to_process = [bfs_root]

    while to_process:
        result.extend(to_process)
        to_process = tree['child'][np.in1d(tree['parent'], to_process)].tolist()

    return result

class CondensedTree (object):

    def __init__(self, condensed_tree_array):
        self._raw_tree = condensed_tree_array

    def get_plot_data(self, leaf_separation=1, log_size=False):
        leaves = get_leaves(self._raw_tree)
        last_leaf = self._raw_tree['parent'].max()
        root = self._raw_tree['parent'].min()

        # We want to get the x and y coordinates for the start of each cluster
        # Initialize the leaves, since we know where they go, the iterate
        # through everything from the leaves back, setting coords as we go
        cluster_x_coords = dict(zip(leaves, [leaf_separation * x
                                             for x in range(len(leaves))]))
        cluster_y_coords = {root : 0.0}

        for cluster in range(last_leaf, root - 1, -1):
            split = self._raw_tree[['child', 'lambda']]
            split = split[(self._raw_tree['parent'] == cluster) & 
                          (self._raw_tree['child_size'] > 1)]
            if len(split['child']) > 1:
                left_child, right_child = split['child']
                cluster_x_coords[cluster] = np.mean([cluster_x_coords[left_child],
                                                     cluster_x_coords[right_child]])
                cluster_y_coords[left_child] = split['lambda'][0]
                cluster_y_coords[right_child] = split['lambda'][1]
            
        # We use bars to plot the 'icicles', so we need to generate centers, tops, 
        # bottoms and widths for each rectangle. We can go through each cluster 
        # and do this for each in turn.
        bar_centers = []
        bar_tops = []
        bar_bottoms = []
        bar_widths = []

        cluster_bounds = {}

        scaling = np.sum(self._raw_tree[self._raw_tree['parent'] == root]['child_size'])

        if log_size:
            scaling = np.log(scaling)

        for c in range(last_leaf, root - 1, -1):
            
            cluster_bounds[c] = [0, 0, 0, 0]
            
            c_children = self._raw_tree[self._raw_tree['parent'] == c]
            current_size = np.sum(c_children['child_size'])
            current_lambda = cluster_y_coords[c]

            if log_size:
                current_size = np.log(current_size)

            cluster_bounds[c][CB_LEFT] = cluster_x_coords[c] * scaling - (current_size / 2.0)
            cluster_bounds[c][CB_RIGHT] = cluster_x_coords[c] * scaling + (current_size / 2.0)
            cluster_bounds[c][CB_BOTTOM] = cluster_y_coords[c]
            cluster_bounds[c][CB_TOP] = np.max(c_children['lambda'])

            for i in np.argsort(c_children['lambda']):
                row = c_children[i]
                if row['lambda'] != current_lambda:
                    bar_centers.append(cluster_x_coords[c] * scaling)
                    bar_tops.append(row['lambda'] - current_lambda)
                    bar_bottoms.append(current_lambda)
                    bar_widths.append(current_size)
                if log_size:
                    current_size = np.log(np.exp(current_size) - row['child_size'])
                else:
                    current_size -= row['child_size']
                current_lambda = row['lambda']

        # Finally we need the horizontal lines that occur at cluster splits.
        line_xs = []
        line_ys = []

        for row in self._raw_tree[self._raw_tree['child_size'] > 1]:
            parent = row['parent']
            child = row['child']
            child_size = row['child_size']
            if log_size:
                child_size = np.log(child_size)
            sign = np.sign(cluster_x_coords[child] - cluster_x_coords[parent])
            line_xs.append([
                cluster_x_coords[parent] * scaling,
                cluster_x_coords[child] * scaling + sign * (child_size / 2.0)
            ])
            line_ys.append([
                cluster_y_coords[child], 
                cluster_y_coords[child]
            ])
            
        return {
            'bar_centers' : bar_centers,
            'bar_tops' : bar_tops,
            'bar_bottoms' : bar_bottoms,
            'bar_widths' : bar_widths,
            'line_xs' : line_xs,
            'line_ys' : line_ys,
            'cluster_bounds': cluster_bounds
        }

    def _select_clusters(self):
        stability = compute_stability(self._raw_tree)
        node_list = sorted(stability.keys(), reverse=True)[:-1]
        cluster_tree = self._raw_tree[self._raw_tree['child_size'] > 1]
        is_cluster = {cluster : True for cluster in node_list}

        for node in node_list:
            child_selection = (cluster_tree['parent'] == node)
            subtree_stability = np.sum([stability[child] for 
                                        child in cluster_tree['child'][child_selection]])

            if subtree_stability > stability[node]:
                is_cluster[node] = False
                stability[node] = subtree_stability
            else:
                for sub_node in bfs_from_cluster_tree(cluster_tree, node):
                    if sub_node != node:
                        is_cluster[sub_node] = False

        return [cluster for cluster in is_cluster if is_cluster[cluster]]
            
    def plot(self, leaf_separation=1, cmap='Blues', select_clusters=False, 
             axis=None, colorbar=True, log_size=False):
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError('You must install the matplotlib library to plot the condensed tree. Use get_plot_data to calculate the relevant data without plotting.')
        
        plot_data = self.get_plot_data(leaf_separation=leaf_separation, log_size=log_size)

        if cmap != 'none':
            sm = plt.cm.ScalarMappable(cmap=cmap, 
                                   norm=plt.Normalize(0, max(plot_data['bar_widths'])))
            sm.set_array(plot_data['bar_widths'])
            bar_colors = [sm.to_rgba(x) for x in plot_data['bar_widths']]
        else:
            bar_colors = 'black'
        
        if axis is None:
            axis = plt.gca()

        axis.bar(
            plot_data['bar_centers'],
            plot_data['bar_tops'],
            bottom=plot_data['bar_bottoms'],
            width=plot_data['bar_widths'],
            color=bar_colors,
            align='center',
            linewidth=0
        )

        for xs, ys in zip(plot_data['line_xs'], plot_data['line_ys']):
            axis.plot(xs, ys, color='black', linewidth=1)
        if select_clusters:
            try:
                from matplotlib.patches import Ellipse
            except ImportError:
                raise ImportError('You must have matplotlib.patches available to plot selected clusters.')

            chosen_clusters = self._select_clusters()
            
            for c in chosen_clusters:
                c_bounds = plot_data['cluster_bounds'][c]
                width = (c_bounds[CB_RIGHT] - c_bounds[CB_LEFT])
                height = (c_bounds[CB_TOP] - c_bounds[CB_BOTTOM])
                center = (
                    np.mean([c_bounds[CB_LEFT], c_bounds[CB_RIGHT]]),
                    np.mean([c_bounds[CB_TOP], c_bounds[CB_BOTTOM]]),
                )

                box = Ellipse(
                    center,
                    2.0 * width,
                    1.2 * height,
                    facecolor='none',
                    edgecolor='r',
                    linewidth=2
                )

                axis.add_artist(box)
                
        if colorbar:
            cb = plt.colorbar(sm)
            if log_size:
                cb.ax.set_ylabel('log(Number of points)')
            else:
                cb.ax.set_ylabel('Number of points')

        axis.set_xticks([])
        for side in ('right', 'top', 'bottom'):
            axis.spines[side].set_visible(False)
        axis.invert_yaxis()
        axis.set_ylabel('$\lambda$ value')

        return axis

    def to_pandas(self):
        try:
            from pandas import DataFrame, Series
        except ImportError:
            raise ImportError('You must have pandas installed to export pandas DataFrames')

        result = DataFrame(self._raw_tree)

        return result

    def to_networkx(self):
        try:
            from networkx import DiGraph, set_node_attributes
        except ImportError:
            raise ImportError('You must have networkx installed to export networkx graphs')

        result = DiGraph()
        for row in self._raw_tree:
            result.add_edge(row['parent'], row['child'], weight=row['lambda'])

        set_node_attributes(result, 'size', dict(self._raw_tree[['child', 'child_size']]))

        return result
                    
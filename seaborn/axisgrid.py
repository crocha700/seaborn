from itertools import product
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt

from . import utils


class FacetGrid(object):

    def __init__(self, data, row=None, col=None, hue=None, col_wrap=None,
                 sharex=True, sharey=True, size=3, aspect=1, palette="husl",
                 row_order=None, col_order=None, hue_order=None,
                 dropna=True, legend=True, legend_out=True, despine=True,
                 margin_titles=False, xlim=None, ylim=None):
        """Initialize the plot figure and FacetGrid object.

        Parameters
        ----------
        data : DataFrame
            Tidy (long-form) dataframe where each column is a variable and
            each row is an observation.
        row, col, hue : strings, optional
            Variable (column) names to subset the data for the facets.
        col_wrap : int, optional
            Wrap the column variable at this width. Incompatible with `row`.
        share{x, y}: booleans, optional
            Lock the limits of the vertical and horizontal axes across the
            facets.
        size : scalar, optional
            Height (in inches) of each facet.
        aspect : scalar, optional
            Aspect * size gives the width (in inches) of each facet.
        palette : dict or seaborn color palette
            Set of colors for mapping the `hue` variable. If a dict, keys
            should be values  in the `hue` variable.
        {row, col, hue}_order: sequence of strings
            Order to plot the values in the faceting variables in, otherwise
            sorts the unique values.
        dropna : boolean, optional
            Drop missing values from the data before plotting.
        legend : boolean, optional
            Draw a legend for the data when using a `hue` variable.
        legend_out: boolean, optional
            Draw the legend outside the grid of plots.
        despine : boolean, optional
            Remove the top and right spines from the plots.
        margin_titles : boolean, optional
            Write the column and row variable labels on the margins of the
            grid rather than above each plot.
        {x, y}lim: tuples, optional
            Limits for each of the axes on each facet when share{x, y} is True.

        Returns
        -------
        FacetGrid

        """
        # Compute the grid shape
        nrow = 1 if row is None else len(data[row].unique())
        ncol = 1 if col is None else len(data[col].unique())

        if col_wrap is not None:
            ncol = col_wrap
            nrow = int(np.ceil(len(data[col].unique()) / col_wrap))

        # Calculate the base figure size
        # This can get stretched later by a legend
        figsize = (ncol * size * aspect, nrow * size)

        # Validate some inputs
        if col_wrap is not None:
            margin_titles = False

        # Build the subplot keyword dictionary
        subplot_kw = {}
        if xlim is not None:
            subplot_kw["xlim"] = xlim
        if ylim is not None:
            subplot_kw["ylim"] = ylim

        # Initialize the subplot grid
        fig, axes = plt.subplots(nrow, ncol, figsize=figsize, squeeze=False,
                                 sharex=sharex, sharey=sharey,
                                 subplot_kw=subplot_kw)

        # Determine the hue facet layer information
        hue_var = hue
        if hue is None:
            hue_names = None
            hue_masks = [np.repeat(True, len(data))]
            # Use the first color of the current palette
            # I'm not sure if I like this vs. e.g. dark gray
            colors = utils.color_palette(n_colors=1)
        else:
            if hue_order is None:
                hue_names = np.sort(data[hue].unique())
            else:
                hue_names = hue_order
            if dropna:
                # Filter NA from the list of unique hue names
                hue_names = list(filter(pd.notnull, hue_names))
            if isinstance(palette, dict):
                # Allow for palette to map from hue variable names
                palette = [palette[h] for h in hue_names]
            hue_masks = [data[hue] == val for val in hue_names]
            colors = utils.color_palette(palette, len(hue_masks))

        # Make a boolean mask that is True anywhere there is an NA
        # value in one of the faceting variables, but only if dropna is True
        none_na = np.zeros(len(data), np.bool)
        if dropna:
            row_na = none_na if row is None else data[row].isnull()
            col_na = none_na if col is None else data[col].isnull()
            hue_na = none_na if hue is None else data[hue].isnull()
            not_na = ~(row_na | col_na | hue_na)
        else:
            not_na = ~none_na

        # Set up the lists of names for the row and column facet variables
        if row is None:
            row_names = []
        elif row_order is None:
            row_names = sorted(data[row].unique())
        else:
            row_names = row_order
        if dropna:
            row_names = list(filter(pd.notnull, row_names))

        if col is None:
            col_names = []
        elif col_order is None:
            col_names = sorted(data[col].unique())
        else:
            col_names = col_order
        if dropna:
            col_names = list(filter(pd.notnull, col_names))

        # Set up the class attributes
        # ---------------------------

        # First the public API
        self.data = data
        self.fig = fig
        self.axes = axes

        self.row_names = row_names
        self.col_names = col_names
        self.hue_names = hue_names

        # Next the private variables
        self._nrow = nrow
        self._row_var = row
        self._ncol = ncol
        self._col_var = col

        self._margin_titles = margin_titles
        self._col_wrap = col_wrap
        self._hue_var = hue_var
        self._colors = colors
        self._draw_legend = ((hue is not None and hue not in [col, row])
                             and legend)
        self._legend_out = legend_out
        self._legend = None
        self._legend_data = {}
        self._x_var = None
        self._y_var = None
        self._dropna = dropna
        self._not_na = not_na

        # Make the axes look good
        fig.tight_layout()
        if despine:
            self.despine()

    def facet_data(self):
        """Generator for name indices and data subsets for each facet.

        Yields
        ------
        (i, j, k), data_ijk : tuple of ints, DataFrame
            The ints provide an index into the {row, col, hue}_names attribute,
            and the dataframe contains a subset of the full data corresponding
            to each facet. The generator yields subsets that correspond with
            the self.axes.flat iterator, or self.axes[i, j] when `col_wrap`
            is None.

        """
        data = self.data

        # Construct masks for the row variable
        if self._nrow == 1 or self._col_wrap is not None:
            row_masks = [np.repeat(True, len(self.data))]
        else:
            row_masks = [data[self._row_var] == n for n in self.row_names]

        # Construct masks for the column variable
        if self._ncol == 1:
            col_masks = [np.repeat(True, len(self.data))]
        else:
            col_masks = [data[self._col_var] == n for n in self.col_names]

        # Construct masks for the hue variable
        if len(self._colors) == 1:
            hue_masks = [np.repeat(True, len(self.data))]
        else:
            hue_masks = [data[self._hue_var] == n for n in self.hue_names]

        # Here is the main generator loop
        for (i, row), (j, col), (k, hue) in product(enumerate(row_masks),
                                                    enumerate(col_masks),
                                                    enumerate(hue_masks)):
            data_ijk = data[row & col & hue & self._not_na]
            yield (i, j, k), data_ijk

    def map(self, func, *args, **kwargs):
        """Apply a plotting function to each facet's subset of the data.

        Parameters
        ----------
        func : callable
            A plotting function that takes data and keyword arguments. It
            must plot to the currently active matplotlib Axes and take a
            `color` keyword argument. If faceting on the `hue` dimension,
            it must also take a `label` keyword argument.
        args : strings
            Column names in self.data that identify variables with data to
            plot. The data for each variable is passed to `func` in the
            order the variables are specified in the call.
        kwargs : keyword arguments
            All keyword arguments are passed to the plotting function.

        Returns
        -------
        self : object
            Returns self.

        """
        # If color was a keyword argument, grab it here
        kw_color = kwargs.pop("color", None)

        # Iterate over the data subsets
        for (row_i, col_j, hue_k), data_ijk in self.facet_data():

            # If this subset is null, move on
            if not data_ijk.values.tolist():
                continue

            # Get the current axis
            ax = self.facet_axis(row_i, col_j)

            # Decide what color to plot with
            kwargs["color"] = self._facet_color(hue_k, kw_color)

            # Insert a label in the keyword arguments for the legend
            if self._hue_var is not None:
                kwargs["label"] = self.hue_names[hue_k]

            # Get the actual data we are going to plot with
            plot_data = data_ijk[list(args)]
            if self._dropna:
                plot_data = plot_data.dropna()
            plot_args = [v for k, v in plot_data.iteritems()]

            # Some matplotlib functions don't handle pandas objects correctly
            if func.__module__.startswith("matplotlib"):
                plot_args = [v.values for v in plot_args]

            # Draw the plot
            self._facet_plot(func, ax, plot_args, kwargs)

        # Finalize the annotations and layout
        self._finalize_grid(args[:2])

        return self

    def map_dataframe(self, func, *args, **kwargs):
        """Like `map` but passes args as strings and inserts data in kwargs.

        This method is suitable for plotting with functions that accept a
        long-form DataFrame as a `data` keyword argument and access the
        data in that DataFrame using string variable names.

        Parameters
        ----------
        func : callable
            A plotting function that takes data and keyword arguments. Unlike
            the `map` method, a function used here must "understand" Pandas
            objects. It also must plot to the currently active matplotlib Axes
            and take a `color` keyword argument. If faceting on the `hue`
            dimension, it must also take a `label` keyword argument.
        args : strings
            Column names in self.data that identify variables with data to
            plot. The data for each variable is passed to `func` in the
            order the variables are specified in the call.
        kwargs : keyword arguments
            All keyword arguments are passed to the plotting function.

        Returns
        -------
        self : object
            Returns self.

        """

        # If color was a keyword argument, grab it here
        kw_color = kwargs.pop("color", None)

        # Iterate over the data subsets
        for (row_i, col_j, hue_k), data_ijk in self.facet_data():

            # If this subset is null, move on
            if not data_ijk.values.tolist():
                continue

            # Get the current axis
            ax = self.facet_axis(row_i, col_j)

            # Decide what color to plot with
            kwargs["color"] = self._facet_color(hue_k, kw_color)

            # Insert a label in the keyword arguments for the legend
            if self._hue_var is not None:
                kwargs["label"] = self.hue_names[hue_k]

            # Stick the facet dataframe into the kwargs
            if self._dropna:
                data_ijk = data_ijk.dropna()
            kwargs["data"] = data_ijk

            # Draw the plot
            self._facet_plot(func, ax, args, kwargs)

        # Finalize the annotations and layout
        self._finalize_grid(args[:2])

        return self

    def _facet_color(self, hue_index, kw_color):

        color = self._colors[hue_index]
        if kw_color is not None:
            return kw_color
        elif color is not None:
            return color

    def _facet_plot(self, func, ax, plot_args, plot_kwargs):

        # Draw the plot
        func(*plot_args, **plot_kwargs)

        # Sort out the supporting information
        self._update_legend_data(ax)
        self._clean_axis(ax)

    def _finalize_grid(self, axlabels):
        """Finalize the annotations and layout."""
        self.set_axis_labels(*axlabels)
        self.set_titles()
        self.fig.tight_layout()
        if self._draw_legend:
            self.set_legend()

    def facet_axis(self, row_i, col_j):
        """Make the axis identified by these indices active and return it."""

        # Calculate the actual indices of the axes to plot on
        if self._col_wrap is not None:
            ax = self.axes.flat[col_j]
        else:
            ax = self.axes[row_i, col_j]

        # Get a reference to the axes object we want, and make it active
        plt.sca(ax)
        return ax

    def set(self, **kwargs):
        """Set axis attributes on each facet.

        This will call set_{key}({value}) for each keyword argument on every
        facet in the grid.

        """
        for key, val in kwargs.items():
            for ax in self.axes.flat:
                setter = getattr(ax, "set_%s" % key)
                setter(val)

        return self

    def despine(self, **kwargs):
        """Remove axis spines from the facets."""
        utils.despine(self.fig, **kwargs)
        return self

    def set_axis_labels(self, x_var, y_var=None):
        """Set axis labels on the left column and bottom row of the grid."""
        if y_var is not None:
            self._y_var = y_var
            self.set_ylabels(y_var)
        self._x_var = x_var
        self.set_xlabels(x_var)
        return self

    def set_xlabels(self, label=None, **kwargs):
        """Label the x axis on the bottom row of the grid."""
        if label is None:
            label = self._x_var
        for ax in self.axes[-1, :]:
            ax.set_xlabel(label, **kwargs)
        return self

    def set_ylabels(self, label=None, **kwargs):
        """Label the y axis on the left column of the grid."""
        if label is None:
            label = self._y_var
        for ax in self.axes[:, 0]:
            ax.set_ylabel(label, **kwargs)
        return self

    def set_xticklabels(self, labels=None, **kwargs):
        """Set x axis tick labels on the bottom row of the grid."""
        for ax in self.axes[-1, :]:
            if labels is None:
                labels = [l.get_text() for l in ax.get_xticklabels()]
            ax.set_xticklabels(labels, **kwargs)
        return self

    def set_yticklabels(self, labels=None, **kwargs):
        """Set y axis tick labels on the left column of the grid."""
        for ax in self.axes[-1, :]:
            if labels is None:
                labels = [l.get_text() for l in ax.get_yticklabels()]
            ax.set_yticklabels(labels, **kwargs)
        return self

    def set_titles(self, template=None, row_template=None,  col_template=None,
                   **kwargs):
        """Draw titles either above each facet or on the grid margins.

        Parameters
        ----------
        template : string
            Template for all titles with the formatting keys {col_var} and
            {col_name} (if using a `col` faceting variable) and/or {row_var}
            and {row_name} (if using a `row` faceting variable).
        row_template:
            Template for the row variable when titles are drawn on the grid
            margins. Must have {row_var} and {row_name} formatting keys.
        col_template:
            Template for the row variable when titles are drawn on the grid
            margins. Must have {col_var} and {col_name} formatting keys.

        Returns
        -------
        self: object
            Returns self.

        """
        args = dict(row_var=self._row_var, col_var=self._col_var)
        kwargs["size"] = kwargs.pop("size", mpl.rcParams["axes.labelsize"])

        # Establish default templates
        if row_template is None:
            row_template = "{row_var} = {row_name}"
        if col_template is None:
            col_template = "{col_var} = {col_name}"
        if template is None:
            if self._row_var is None:
                template = col_template
            elif self._col_var is None:
                template = row_template
            else:
                template = " | ".join([row_template, col_template])

        if self._margin_titles:
            if self.row_names:
                # Draw the row titles on the right edge of the grid
                for i, row_name in enumerate(self.row_names):
                    ax = self.axes[i, -1]
                    args.update(dict(row_name=row_name))
                    title = row_template.format(**args)
                    trans = self.fig.transFigure.inverted()
                    bbox = ax.bbox.transformed(trans)
                    x = bbox.xmax + 0.01
                    y = bbox.ymax - (bbox.height / 2)
                    self.fig.text(x, y, title, rotation=270,
                                  ha="left", va="center", **kwargs)
            if self.col_names:
                # Draw the column titles  as normal titles
                for j, col_name in enumerate(self.col_names):
                    args.update(dict(col_name=col_name))
                    title = col_template.format(**args)
                    self.axes[0, j].set_title(title, **kwargs)

            return self

        # Otherwise title each facet with all the necessary information
        if (self._row_var is not None) and (self._col_var is not None):
            for i, row_name in enumerate(self.row_names):
                for j, col_name in enumerate(self.col_names):
                    args.update(dict(row_name=row_name, col_name=col_name))
                    title = template.format(**args)
                    self.axes[i, j].set_title(title, **kwargs)
        elif self.row_names:
            for i, row_name in enumerate(self.row_names):
                args.update(dict(row_name=row_name))
                title = template.format(**args)
                self.axes[i, 0].set_title(title, **kwargs)
        elif self.col_names:
            for i, col_name in enumerate(self.col_names):
                args.update(dict(col_name=col_name))
                title = template.format(**args)
                # Index the flat array so col_wrap works
                self.axes.flat[i].set_title(title, **kwargs)
        return self

    def set_legend(self, legend_data=None, title=None):
        """Draw a legend, possibly resizing the figure."""
        # Find the data for the legend
        legend_data = self._legend_data if legend_data is None else legend_data
        labels = sorted(self._legend_data.keys())
        handles = [legend_data[l] for l in labels]
        title = self._hue_var if title is None else title
        title_size = mpl.rcParams["axes.labelsize"] * .85

        if self._legend_out:
            # Draw a full-figure legend outside the grid
            figlegend = plt.figlegend(handles, labels, "center right",
                                      scatterpoints=1)
            self._legend = figlegend
            figlegend.set_title(self._hue_var, prop={"size": title_size})

            # Draw the plot to set the bounding boxes correctly
            plt.draw()

            # Calculate and set the new width of the figure so the legend fits
            legend_width = figlegend.get_window_extent().width / self.fig.dpi
            figure_width = self.fig.get_figwidth()
            self.fig.set_figwidth(figure_width + legend_width)

            # Draw the plot again to get the new transformations
            plt.draw()

            # Now calculate how much space we need on the right side
            legend_width = figlegend.get_window_extent().width / self.fig.dpi
            space_needed = legend_width / (figure_width + legend_width)
            margin = .04 if self._margin_titles else .01
            self._space_needed = margin + space_needed
            right = 1 - self._space_needed

            # Place the subplot axes to give space for the legend
            self.fig.subplots_adjust(right=right)

        else:
            # Draw a legend in the first axis
            leg = self.axes[0, 0].legend(handles, labels, loc="best")
            leg.set_title(self._hue_var, prop={"size": title_size})

    def _clean_axis(self, ax):
        """Turn off axis labels and legend."""
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.legend_ = None
        return self

    def _update_legend_data(self, ax):
        """Extract the legend data from an axes object and save it."""
        handles, labels = ax.get_legend_handles_labels()
        data = {l: h for h, l in zip(handles, labels)}
        self._legend_data.update(data)

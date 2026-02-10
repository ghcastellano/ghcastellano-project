/**
 * Paginator - Reusable client-side pagination component.
 *
 * DOM mode (Jinja-rendered tables/lists):
 *   new Paginator({
 *     container: '#inspectionList',
 *     itemSelector: '.inspection-item',
 *     controlsTarget: '#paginationControls',
 *     perPage: 10,
 *   });
 *
 * Array mode (AJAX data):
 *   const p = new Paginator({
 *     controlsTarget: '#controls',
 *     perPage: 10,
 *     mode: 'array',
 *     renderCallback: (pageItems) => { ... },
 *   });
 *   p.setData(jsonArray);
 */
class Paginator {
    constructor(options) {
        this.container = options.container
            ? document.querySelector(options.container)
            : null;
        this.itemSelector = options.itemSelector || 'tr';
        this.controlsTarget = document.querySelector(options.controlsTarget);
        this.perPage = options.perPage || 10;
        this.perPageOptions = options.perPageOptions || [10, 25, 50, 0];
        this.currentPage = 1;
        this.mode = options.mode || 'dom';
        this.renderCallback = options.renderCallback || null;
        this.data = [];
        this.skipSelector = options.skipSelector || null;
        this.onPageChange = options.onPageChange || null;
        this._allItems = [];

        if (this.mode === 'dom' && this.container) {
            this._initDom();
        }
    }

    _initDom() {
        this._cacheItems();
        this._render();
    }

    _cacheItems() {
        if (!this.container) return;
        this._allItems = Array.from(
            this.container.querySelectorAll(this.itemSelector)
        );
    }

    _getVisibleItems() {
        if (this.mode === 'array') return this.data;
        return this._allItems.filter(function(item) {
            return !item.hasAttribute('data-filter-hidden');
        });
    }

    get totalPages() {
        var items = this._getVisibleItems();
        if (this.perPage === 0) return 1;
        return Math.max(1, Math.ceil(items.length / this.perPage));
    }

    get totalItems() {
        return this._getVisibleItems().length;
    }

    setData(arr) {
        this.data = arr || [];
        if (this.currentPage > this.totalPages) this.currentPage = 1;
        this._render();
    }

    goToPage(page) {
        page = Math.max(1, Math.min(page, this.totalPages));
        this.currentPage = page;
        this._render();
        if (this.onPageChange) this.onPageChange(page);
    }

    setPerPage(n) {
        this.perPage = parseInt(n);
        this.currentPage = 1;
        this._render();
    }

    refresh() {
        if (this.mode === 'dom') this._cacheItems();
        if (this.currentPage > this.totalPages) this.currentPage = 1;
        this._render();
    }

    _render() {
        if (this.mode === 'dom') {
            this._renderDom();
        } else {
            this._renderArray();
        }
        this._renderControls();
    }

    _renderDom() {
        var visibleItems = this._getVisibleItems();
        var start = this.perPage === 0 ? 0 : (this.currentPage - 1) * this.perPage;
        var end = this.perPage === 0 ? visibleItems.length : start + this.perPage;

        visibleItems.forEach(function(item, idx) {
            if (idx >= start && idx < end) {
                item.style.display = '';
                item.removeAttribute('data-paginator-hidden');
            } else {
                item.style.display = 'none';
                item.setAttribute('data-paginator-hidden', 'true');
            }
        });

        // Handle group headers: show only if group has visible rows
        if (this.skipSelector && this.container) {
            var self = this;
            var headers = this.container.querySelectorAll(this.skipSelector);
            headers.forEach(function(header) {
                var next = header.nextElementSibling;
                var hasVisible = false;
                while (next && !next.matches(self.skipSelector)) {
                    if (next.style.display !== 'none') hasVisible = true;
                    next = next.nextElementSibling;
                }
                header.style.display = hasVisible ? '' : 'none';
            });
        }
    }

    _renderArray() {
        if (!this.renderCallback) return;
        var start = this.perPage === 0 ? 0 : (this.currentPage - 1) * this.perPage;
        var end = this.perPage === 0 ? this.data.length : start + this.perPage;
        this.renderCallback(this.data.slice(start, end), this.data);
    }

    _renderControls() {
        if (!this.controlsTarget) return;
        var total = this.totalItems;
        var totalPages = this.totalPages;

        if (total === 0) {
            this.controlsTarget.innerHTML = '';
            return;
        }

        var start = this.perPage === 0 ? 1 : ((this.currentPage - 1) * this.perPage) + 1;
        var end = this.perPage === 0 ? total : Math.min(this.currentPage * this.perPage, total);

        // Per-page options
        var perPageOpts = this.perPageOptions.map(function(n) {
            var label = n === 0 ? 'Todos' : n;
            var selected = n === this.perPage ? 'selected' : '';
            return '<option value="' + n + '" ' + selected + '>' + label + '</option>';
        }.bind(this)).join('');

        // Page buttons
        var pageButtons = '';
        var maxVisible = 5;
        var startPage = Math.max(1, this.currentPage - Math.floor(maxVisible / 2));
        var endPage = Math.min(totalPages, startPage + maxVisible - 1);
        if (endPage - startPage < maxVisible - 1) {
            startPage = Math.max(1, endPage - maxVisible + 1);
        }

        if (startPage > 1) {
            pageButtons += '<button class="pg-btn" data-page="1">1</button>';
            if (startPage > 2) pageButtons += '<span class="pg-ellipsis">...</span>';
        }
        for (var i = startPage; i <= endPage; i++) {
            var active = i === this.currentPage ? 'pg-btn-active' : '';
            pageButtons += '<button class="pg-btn ' + active + '" data-page="' + i + '">' + i + '</button>';
        }
        if (endPage < totalPages) {
            if (endPage < totalPages - 1) pageButtons += '<span class="pg-ellipsis">...</span>';
            pageButtons += '<button class="pg-btn" data-page="' + totalPages + '">' + totalPages + '</button>';
        }

        this.controlsTarget.innerHTML =
            '<div class="pagination-wrapper">' +
                '<div class="pagination-info">' +
                    'Exibindo <strong>' + start + '-' + end + '</strong> de <strong>' + total + '</strong>' +
                '</div>' +
                '<div class="pagination-nav">' +
                    '<button class="pg-btn pg-btn-nav" data-page="prev" ' +
                        (this.currentPage <= 1 ? 'disabled' : '') + '>' +
                        '&laquo; Anterior' +
                    '</button>' +
                    pageButtons +
                    '<button class="pg-btn pg-btn-nav" data-page="next" ' +
                        (this.currentPage >= totalPages ? 'disabled' : '') + '>' +
                        'Pr\u00f3ximo &raquo;' +
                    '</button>' +
                '</div>' +
                '<div class="pagination-per-page">' +
                    '<select class="pg-select" data-action="perPage">' +
                        perPageOpts +
                    '</select>' +
                    '<span>por p\u00e1gina</span>' +
                '</div>' +
            '</div>';

        // Attach events
        var self = this;
        this.controlsTarget.querySelectorAll('[data-page]').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var val = this.dataset.page;
                if (val === 'prev') self.goToPage(self.currentPage - 1);
                else if (val === 'next') self.goToPage(self.currentPage + 1);
                else self.goToPage(parseInt(val));
            });
        });
        var perPageSelect = this.controlsTarget.querySelector('[data-action="perPage"]');
        if (perPageSelect) {
            perPageSelect.addEventListener('change', function() {
                self.setPerPage(this.value);
            });
        }
    }
}

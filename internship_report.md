# Internship Report - ElevanceSkills

**Task 1: Scalable Genre and Language Filtering with Query Optimization**

## 1. Introduction
The objective of this assignment was to implement advanced, scalable filtering for a movie catalog capable of handling 5,000+ entries. The system needed to support multi-select filtering by genre and language on the server-side, maintain dynamic and accurate filter counts (faceted search), implement pagination, sort data, and ensure high query performance by avoiding full-table scans. This task was integrated directly into the `djnago-bookmyshow-clone` project.

## 2. Background
The existing BookMyShow clone possessed rudimentary text-based search functionality with no indexing strategy. As the catalog scales to 5,000+ movies, loading `Movie.objects.all()` into memory is unsustainable and leads to `N+1` query inefficiencies when iterating over templates. A database-level approach utilizing advanced Django ORM aggregations was required.

## 3. Learning Objectives
* Understand and implement Many-to-Many relationships effectively.
* Utilize database indexing to optimize search and filtering performance.
* Master Django ORM functions including `Q` objects, `annotate`, `Count`, and `prefetch_related`.
* Understand pagination to reduce server memory footprint.
* Learn tradeoffs between scalability (caching vs database queries) and flexibility (dynamic filter counts).

## 4. Activities and Tasks
* **Database Schema Update**: Extracted `Genre` and `Language` into dedicated models. Linked them to the `Movie` model using `ManyToManyField`.
* **Indexing Strategy**: Applied `db_index=True` to the `name` column across the `Movie`, `Genre`, and `Language` models to optimize `WHERE` clauses during filtering.
* **Backend View Optimization (`movie_list`)**:
    * Implemented `prefetch_related('genres', 'languages')` to prevent the `N+1` problem.
    * Engineered multi-select filtering mechanisms using Django ORM `.filter(name__in=...)` chained logic for complex conditional rendering.
    * Implemented dynamic filter counts utilizing `annotate(Count('movies', filter=Q(movies__in=active_movies), distinct=True))`. This counts occurrences dynamically based on the current search matrix.
* **Pagination & Sorting**: Implemented `Paginator` restricting memory loading to 20 objects at once. Developed dynamic sorting via `order_by()`.
* **Frontend Overhaul (`movie_list.html`)**: Integrated a modern glassmorphic "Cinematic Dark Mode" UI. Engineered a faceted sidebar that retains state across pagination and sort clicks.

## 5. Skills and Competencies
* **Advanced Query Design**: Gained expertise analyzing SQL queries and applying database-level aggregations rather than Python-level loops.
* **Performance Tuning**: Recognized the necessity of `prefetch_related` when rendering multi-relational queries in templates.
* **Frontend Integration**: Enhanced user experience securely retaining query parameters (`?search=a&genres=Action&page=2`) using hidden `<input>` elements within the DOM.

## 6. Challenges and Solutions
**Challenge**: Calculating dynamic filter counts for 5,000+ movies dynamically. 
*Naive Approach*: Iterating all movies in Python and building a frequency dictionary (leads to CPU bottleneck and memory spikes).
*Solution*: Handled directly in SQL via Django's `annotate(Count(...))`. While this creates subqueries, filtering against the indexed `id` field of the active movie queryset (`Q(movies__in=active_movies)`) proved highly scalable and shifted computational load back to the RDBMS layer where it belongs.

**Challenge**: N+1 Query Problem in Templates.
*Naive Approach*: Calling `{{ movie.genres.all }}` in a loop executes a new database query per movie.
*Solution*: Explicitly invoked `.prefetch_related('genres')` in the base queryset to fetch all associations utilizing batched SQL `IN` lookups.

## 7. Outcomes and Impact
The platform can now sustain extensive scaling. A generated dataset of 5,000 synthetic movies with multiple relation arrays navigates seamlessly. Query times remain consistently flat regardless of catalog size due to explicit indexing on names and Django Paginator ensuring the DB uses `LIMIT` and `OFFSET` appropriately. 

## 8. Conclusion
The implementation successfully resolves the scalability requirement while enhancing user flexibility. Proper database indexing, coupled with correct ORM invocation (`prefetch`, `annotate`, `Q`), transforms an inherently $O(N)$ operation into highly optimized relational lookups. The integration aligns perfectly with ElevanceSkills requirements prohibiting full-table scans while dynamically maintaining precise filter aggregation thresholds.

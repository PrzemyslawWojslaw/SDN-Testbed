import numpy as np

from sklearn.cluster import KMeans, SpectralClustering, DBSCAN, OPTICS, AffinityPropagation, Birch
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics import calinski_harabasz_score
from kneed import KneeLocator

from tools import messages

class ClusteringResult():
    def __init__(self, path, features):
        self.pcapPath = path
        self.pcapFeatures = features
        self.cluster = None
        self.cllusterBeforeNormalization = None
        self.hostPair = None


class SupportCluster():  # support classs for equal distribiution of packets (when algorithm found more clusters than required)
    def __init__(self, label):
        self.label = label
        self.size = 0  # size - number of packets


class ClusteringEngine():
    def __init__(self):
        self.results = []  # list of ClusteringResult objects
        self.clustersSize = []   # list of SupportCluster objects
        self.hostPairs = {}  # dict { number/cluster : (host1, host2) }

    def getResults(self):
        if self.results is None:
            messages.error("Engine does not have any results. Maybe was not started yet?")
        else:
            return self.results

    def updateFeatures(self, pcapsFeatures):
        self.results.clear()
        for key, value in pcapsFeatures.items():  # dictionary { "pcap_path" : dict{pcap_features} } - features listed in featureExtraction.py
            result = ClusteringResult(path=key, features=value)
            self.results.append(result)

    def updateHostPairs(self, hostPairs):
        self.hostPairs = hostPairs

    def start(self, mode="K-means", restart=False):
        if not self.results:
            messages.error("No \".pcap\" files given to engine.")
            return None

        if not self.hostPairs:
            messages.error("No host pairs given to engine.")
        cluster_number = len(self.hostPairs)

        if self.results[0].cluster and not restart:  # if self.results[0].cluster is not None ...
            return self.results

        data = []

        for result in self.results:
            feature_value_list = []
            for feature_value in result.pcapFeatures.values():
                feature_value_list.append(feature_value)
            data.append(feature_value_list)

        if mode == 1 or mode == "K-means":
            kmeans = KMeans(n_clusters=cluster_number)
            ready = False
            while not ready:
                try:
                    kmeans.fit(data)
                    ready = True
                except ValueError as error:
                    print("Value error: " + str(error))
                    print(data)
                    data.reshape(1, -1)  # ValueError: Expected 2D array, got 1D array instead:
                    # array=[].
                    # Reshape your data either using array.reshape(-1, 1) if your data has a single feature or array.reshape(1, -1) if it contains a single sample.

            clustering_labels = kmeans.predict(data)
        elif mode == 2 or mode == "Spectral clustering":
            spectral = SpectralClustering(n_clusters=cluster_number)
            clustering_labels = spectral.fit_predict(data)
        elif mode == 3 or mode == "DBSCAN":
            eps = self.__estimateEps(data)
            samples = self.__estimateSamples(data, eps)

            dbscan = DBSCAN(eps=eps, min_samples=samples)
            clustering_labels = dbscan.fit_predict(data)
            if -1 in clustering_labels:   # change noise label from -1 to 0
                clustering_labels = [ x + 1 for x in clustering_labels]
        elif mode == 4 or mode == "OPTICS":
            optics = OPTICS(min_samples=2)
            clustering_labels = optics.fit_predict(data)
            if -1 in clustering_labels:  # change noise label from -1 to 0
                clustering_labels = [ x + 1 for x in clustering_labels]
        elif mode == 5 or mode == "Affinity propagation":
            affinity = AffinityPropagation(random_state=5)
            clustering_labels = affinity.fit_predict(data)
        elif mode == 6 or mode == "Birch":
            brc = Birch(n_clusters=5)
            clustering_labels = brc.fit_predict(data)
        else:
            messages.error("Unknown clustering algorithm \"" + mode + "\".")
            return None

        self.clustersSize.clear()
        for i in range(len(clustering_labels)):
            self.results[i].cluster = clustering_labels[i]
            found = False
            for cluster in self.clustersSize:
                if cluster.label == clustering_labels[i]:
                    cluster.size += self.results[i].pcapFeatures["packet_count"]
                    found = True
            if not found:
                cluster = SupportCluster(clustering_labels[i])
                cluster.size += self.results[i].pcapFeatures["packet_count"]
                self.clustersSize.append(cluster)

        self.__checkResults(cluster_number)
        return self.results

    def __checkResults(self, cluster_number):
        if len(self.clustersSize) < cluster_number:
            self.start(mode="K-means", restart=True)
        elif len(self.clustersSize) == cluster_number:
            for result in self.results:
                result.clusterBeforeNormalization = result.cluster
                result.hostPair = self.hostPairs[result.cluster]
        else:
            #   Algorithm to combine files into groups of similar size (packet number)
            # Find the target group size. This is the sum of all sizes divided by n.
            # Create a list of sizes.
            # Sort the files decreasing in size.
            # for each group
            #     while the remaining space in your group is bigger than the first element of the list
            #         take the first element of the list and move it to the group
            #     for each element
            #         find the elemnet for which the difference between group size and target group size is minimal
            #     move this elemnt to the group
            sum_of_sizes = 0
            for cluster in self.clustersSize:
                sum_of_sizes += cluster.size

            target_group_size = sum_of_sizes / cluster_number
            self.clustersSize.sort(key=lambda x: x.size, reverse=True)

            cluster_groups = []
            for i in range(cluster_number):
                group = []
                group.append(self.clustersSize[0])  # each new cluster (group) contains one of the biggest previous clusters
                self.clustersSize.pop(0)
                cluster_groups.append(group)

            for group in cluster_groups:
                group_size = group[0].size
                difference_from_target = abs(target_group_size - group_size)  # for stop condition
                while True:
                    if not self.clustersSize:
                        break
                    cluster = min(self.clustersSize, key=lambda x: abs(target_group_size - (group_size + x.size)))
                    new_difference_from_target = abs(target_group_size - (group_size + cluster.size))
                    if new_difference_from_target < difference_from_target:
                        group.append(cluster)
                        self.clustersSize.remove(cluster)
                        group_size += cluster.size
                        difference_from_target = new_difference_from_target
                    else:
                        break

            old_to_new_map = {}
            for i in range(len(cluster_groups)):
                for cluster in cluster_groups[i]:
                    old_to_new_map[cluster.label] = i

            for result in self.results:
                result.clusterBeforeNormalization = result.cluster
                result.cluster = old_to_new_map[result.cluster]
                result.hostPair = self.hostPairs[result.cluster]

    def __estimateEps(self, data):
        neigh = NearestNeighbors(n_neighbors=2)
        nbrs = neigh.fit(data)
        distances, indices = nbrs.kneighbors(data)
        distances = np.sort(distances, axis=0)
        distances = distances[:, 1]

        i = np.arange(len(distances))
        knee = KneeLocator(i, distances, S=1, curve='convex', direction='increasing', interp_method='polynomial')
        return knee.knee

    def __getScore(self, data, eps, center):
        dbscan = DBSCAN(eps=eps, min_samples=center)
        model = dbscan.fit_predict(data)

        # Calculate Score
        try:
            score = calinski_harabasz_score(data, model)
        except ValueError:
            score = 0
        return score

    def __estimateSamples(self, data, eps):
        scores = []
        centers = list(range(2, 30))

        max_score = 0
        samples = 0
        for center in centers:
            score = self.__getScore(data, eps, center)
            scores.append(score)
            if score > max_score:
                max_score = score
                samples = center

        return samples
